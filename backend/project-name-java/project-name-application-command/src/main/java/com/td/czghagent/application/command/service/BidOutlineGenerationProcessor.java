// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-05
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.BidDocument;
import com.td.czghagent.domain.model.BidProductionRules;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.model.CurrentUser;
import com.td.czghagent.domain.model.OperationContext;
import com.td.czghagent.domain.port.TenderAiGateway;
import com.td.czghagent.domain.repository.BidRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class BidOutlineGenerationProcessor {
    private static final int MAX_OUTLINE_REFERENCE_CHARACTERS = 50_000;
    private final BidRepository bidRepository;
    private final BidOutlineStagedPlanner stagedPlanner;
    private final BidAssetIngestionService assetIngestionService;
    private final BidCommandSupport support;

    public BidOutlineGenerationProcessor(
            BidRepository bidRepository,
            BidOutlineStagedPlanner stagedPlanner,
            BidAssetIngestionService assetIngestionService,
            BidCommandSupport support
    ) {
        this.bidRepository = bidRepository;
        this.stagedPlanner = stagedPlanner;
        this.assetIngestionService = assetIngestionService;
        this.support = support;
    }

    public void process(String taskId, String bidId, String ownerId,
                        String traceId, String ipAddress) {
        if (!progress(taskId, "PREPARING", 10)) {
            return;
        }
        BidDocument bid = support.requireBidForTask(bidId, ownerId);
        OperationContext context = context(bid, traceId, ipAddress);
        BidWorkspace workspace = bidRepository.loadWorkspace(bid);
        validateTask(taskId, workspace);
        validate(workspace);
        List<TenderAiGateway.ReferenceSummary> references = referenceSummaries(workspace, context);
        if (!progress(taskId, "GENERATING", 35)) {
            return;
        }
        // 按阶段走，每个阶段的结果落库。重试时从断点继续——不这样做的话，
        // 一次大标书在第十几批失败，重试会从策略开始重跑，把已经成功的那十几批
        // 白白丢掉重新付一遍钱，而且重跑出来的目录和上一次并不相同。
        TenderAiGateway.OutlinePlan plan = stagedPlanner.plan(
                taskId, bidId, new TenderAiGateway.OutlineRequest(
                        traceId, bid.title(), bid.targetPages(), bid.biddingMode(),
                        BidProductionRules.effectiveCriteria(workspace).stream()
                                .map(this::toAiCriterion).toList(), references));
        List<BidWorkspace.OutlineNode> nodes = toNodes(plan);
        if (!progress(taskId, "SAVING", 90)) {
            return;
        }
        // 提示随任务保存：目录规模偏差只提示、不让目录失败，页面据此显示黄色提示。
        if (!bidRepository.completeOutlineTask(taskId, bidId, nodes, plan.warnings())) {
            return;
        }
        support.audit(context, bidId, "BID_OUTLINE_GENERATE",
                "异步生成三级目录，共" + nodes.size() + "个节点");
    }

    public void fail(String taskId, String bidId, String errorMessage) {
        bidRepository.failOutlineTask(taskId, bidId, safeMessage(errorMessage));
    }

    private void validate(BidWorkspace workspace) {
        if (!"FROZEN".equals(workspace.production().interpretationStatus())) {
            throw new BusinessException(
                    "BID_INTERPRETATION_NOT_FROZEN", "请先确认并冻结招标文件解读", 409);
        }
        if (!BidProductionRules.hasCompleteInterpretation(workspace.criteria())) {
            throw new BusinessException(
                    "BID_CRITERIA_REQUIRED", "请先完成项目概述和技术部分评分要求解读", 400);
        }
    }

    private void validateTask(String taskId, BidWorkspace workspace) {
        BidWorkspace.OutlineTask task = workspace.outlineTask();
        if (task == null || !task.id().equals(taskId)
                || workspace.bid().revision() != task.inputRevision() + 1) {
            throw new BusinessException(
                    "BID_OUTLINE_INPUT_CHANGED", "目录生成期间上游内容发生变化，请重新生成", 409);
        }
    }

    private List<BidWorkspace.OutlineNode> toNodes(TenderAiGateway.OutlinePlan plan) {
        Map<String, String> ids = new HashMap<>();
        plan.nodes().forEach(node -> ids.put(node.nodeKey(), UUID.randomUUID().toString()));
        List<BidWorkspace.OutlineNode> nodes = new ArrayList<>();
        for (int index = 0; index < plan.nodes().size(); index++) {
            TenderAiGateway.OutlineNode node = plan.nodes().get(index);
            String title = support.safe(node.title());
            if (title.isBlank() || title.length() > 200) {
                throw new BusinessException(
                        "BID_AI_OUTLINE_INVALID", "AI 返回的目录标题不合法", 502);
            }
            nodes.add(new BidWorkspace.OutlineNode(
                    ids.get(node.nodeKey()),
                    node.parentKey() == null ? null : ids.get(node.parentKey()),
                    node.level(), title, node.level() == 1 ? node.plannedPages() : 0, index, 0,
                    support.safe(node.taskBrief()), support.safeList(node.mustKeywords()), List.of()));
        }
        return nodes;
    }

    private TenderAiGateway.Criterion toAiCriterion(BidWorkspace.Criterion item) {
        return new TenderAiGateway.Criterion(
                item.id(), item.type(), item.title(), item.description(), item.score(),
                item.sourceLocator(), item.sourceExcerpt());
    }

    private List<TenderAiGateway.ReferenceSummary> referenceSummaries(
            BidWorkspace workspace, OperationContext context) {
        List<TenderAiGateway.ReferenceSummary> references = new ArrayList<>();
        for (String assetId : workspace.selectedAssetIds()) {
            BidRepository.AssetRecord asset = bidRepository
                    .findAsset(assetId, context.user().id(), context.user().tenant()).orElse(null);
            if (asset == null || !"OUTLINE".equals(asset.category())) {
                continue;
            }
            List<BidReferenceChunk> chunks = assetIngestionService.ensureIngested(asset);
            StringBuilder summary = new StringBuilder();
            for (BidReferenceChunk chunk : chunks) {
                if (summary.length() >= MAX_OUTLINE_REFERENCE_CHARACTERS) {
                    break;
                }
                summary.append('[').append(chunk.sourceLocator()).append("] ")
                        .append(chunk.content()).append('\n');
            }
            references.add(new TenderAiGateway.ReferenceSummary(
                    asset.id(), asset.category(), asset.originalFileName(), limit(summary.toString())));
        }
        return references;
    }

    private boolean progress(String taskId, String stage, int percentage) {
        return bidRepository.updateOutlineTaskProgress(taskId, stage, percentage);
    }

    /**
     * 为后台执行铸一个操作上下文。
     *
     * <p>租户轴取自<strong>标书本身</strong>而不是由 ownerId 现推：ownerId 只说明归属人，
     * 而一个人可以属于多个工作空间。从人推空间，在多空间场景下会把审计记到错误的空间上，
     * 且不报任何错。
     *
     * <p>显示名与用户名留空：后台路径拿不到，也不该拿——它们只用于界面呈现，
     * 编一个假的会让审计里出现一个查无此人的名字。
     */
    private OperationContext context(BidDocument bid, String traceId, String ipAddress) {
        return new OperationContext(
                new CurrentUser(bid.ownerId(), "", "", "PLANNER", null, bid.tenant()),
                traceId, ipAddress);
    }

    private String limit(String value) {
        return value.length() <= 500_000 ? value : value.substring(0, 500_000);
    }

    private String safeMessage(String message) {
        String value = message == null || message.isBlank() ? "目录生成失败" : message;
        return value.substring(0, Math.min(500, value.length()));
    }
}
