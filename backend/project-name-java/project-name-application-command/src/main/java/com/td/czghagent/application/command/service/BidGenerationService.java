// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-28
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.exception.AiGatewayException;
import com.td.czghagent.domain.model.BidDocument;
import com.td.czghagent.domain.model.BidGenerationPlan;
import com.td.czghagent.domain.model.BidGenerationSnapshot;
import com.td.czghagent.domain.model.BidGenerationUnit;
import com.td.czghagent.domain.model.BidProductionRules;
import com.td.czghagent.domain.model.BidProductionState;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.port.TenderAiGateway;
import com.td.czghagent.domain.repository.BidProductionRepository;
import com.td.czghagent.domain.repository.BidRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class BidGenerationService {
    private static final int MAX_UNIT_REPAIR_ROUNDS = 2;

    private final BidRepository bidRepository;
    private final BidProductionRepository productionRepository;
    private final TenderAiGateway tenderAiGateway;
    private final BidGenerationPlanningService planningService;
    private final BidGenerationExecutionPlanner executionPlanner;
    private final BidUnitDraftFactory draftFactory;
    private final BidBranchBlueprintService blueprintService;
    private final BidAiExecutionService aiExecutionService;
    private final BidContentReviewService reviewService;
    private final BidContentFinalizationService finalizationService;
    private final String providerName;
    private final String modelName;

    public BidGenerationService(
            BidRepository bidRepository,
            BidProductionRepository productionRepository,
            TenderAiGateway tenderAiGateway,
            BidGenerationPlanningService planningService,
            BidGenerationExecutionPlanner executionPlanner,
            BidUnitDraftFactory draftFactory,
            BidBranchBlueprintService blueprintService,
            BidAiExecutionService aiExecutionService,
            BidContentReviewService reviewService,
            BidContentFinalizationService finalizationService
    ) {
        this.bidRepository = bidRepository;
        this.productionRepository = productionRepository;
        this.tenderAiGateway = tenderAiGateway;
        this.planningService = planningService;
        this.executionPlanner = executionPlanner;
        this.draftFactory = draftFactory;
        this.blueprintService = blueprintService;
        this.aiExecutionService = aiExecutionService;
        this.reviewService = reviewService;
        this.finalizationService = finalizationService;
        this.providerName = aiExecutionService.providerName();
        this.modelName = aiExecutionService.fastModelName();
    }

    public GenerationLaunch createTask(BidWorkspace workspace) {
        BidGenerationPlanningService.Launch launch = planningService.create(workspace);
        return new GenerationLaunch(launch.taskId(), launch.snapshotId(), launch.snapshotHash());
    }

    public List<String> prepare(String taskId, String bidId, String ownerId,
                                String snapshotId, String snapshotHash) {
        PreparedGeneration prepared = prepareGeneration(
                taskId, bidId, ownerId, snapshotId, snapshotHash);
        return prepared.units().stream().map(BidGenerationUnit::id).toList();
    }

    public BidGenerationPlan preparePlan(String taskId, String bidId, String ownerId,
                                         String snapshotId, String snapshotHash) {
        PreparedGeneration prepared = prepareGeneration(
                taskId, bidId, ownerId, snapshotId, snapshotHash);
        return executionPlanner.plan(prepared.snapshot(), prepared.units());
    }

    private PreparedGeneration prepareGeneration(
            String taskId, String bidId, String ownerId,
            String snapshotId, String snapshotHash
    ) {
        BidGenerationSnapshot snapshot = requireSnapshot(
                taskId, bidId, ownerId, snapshotId, snapshotHash);
        bidRepository.startGenerationTask(taskId);
        productionRepository.appendEvent(
                taskId, bidId, null, "TASK_STARTED",
                "正文分段生成已开始，输入快照 " + snapshot.snapshotHash().substring(0, 12));
        return new PreparedGeneration(
                snapshot, productionRepository.listGenerationUnits(taskId));
    }

    /**
     * 生成并原子提交一个最小写作单元。
     *
     * <p><b>Preconditions:</b> 单元属于传入任务和不可变快照。</p>
     * <p><b>Side Effects:</b> 调用模型并原子更新单元、章节、版本、进度和审计。</p>
     * <p><b>Error Semantics:</b> 已成功单元直接跳过；失败单元可由 Temporal 重试。</p>
     */
    public void generateUnit(String taskId, String bidId, String ownerId,
                             String snapshotId, String snapshotHash, String unitId) {
        BidGenerationSnapshot snapshot = requireSnapshot(
                taskId, bidId, ownerId, snapshotId, snapshotHash);
        BidGenerationUnit unit = requireUnit(taskId, bidId, unitId);
        if (unit.succeeded() || "SKIPPED".equals(unit.status())) {
            return;
        }
        BidGenerationSnapshot.Outline outline = draftFactory.outlineForChapter(snapshot, unit.chapterId());
        if ("MANUAL".equals(outline.chapterGenerationStatus())) {
            productionRepository.skipGenerationUnit(
                    unit.id(), taskId, bidId, unit.chapterId(), "人工版本已保留");
            return;
        }
        if (!productionRepository.startGenerationUnit(unit.id())) {
            BidGenerationUnit current = requireUnit(taskId, bidId, unitId);
            if (current.succeeded() || "SKIPPED".equals(current.status())) {
                return;
            }
            throw new IllegalStateException("生成单元正在被其他活动处理");
        }
        executeAiUnit(snapshot, requireUnit(taskId, bidId, unitId));
    }

    public void complete(String taskId, String bidId, String ownerId,
                         String snapshotId, String snapshotHash) {
        BidGenerationSnapshot snapshot = requireSnapshot(
                taskId, bidId, ownerId, snapshotId, snapshotHash);
        List<BidGenerationUnit> units = productionRepository.listGenerationUnits(taskId);
        if (units.stream().anyMatch(unit -> !unit.succeeded() && !"SKIPPED".equals(unit.status()))) {
            throw new IllegalStateException("正文任务仍有未完成分段");
        }
        finalizationService.complete(taskId, ownerId, snapshot, units);
    }

    public void reviewNow(String bidId, String ownerId, String requestId) {
        reviewService.reviewNow(bidId, ownerId, requestId);
    }

    public void fail(String taskId, String bidId, String errorMessage) {
        String message = safe(errorMessage, "正文生成失败");
        if (bidRepository.failGenerationTask(
                taskId, bidId, message.substring(0, Math.min(500, message.length())))) {
            productionRepository.appendEvent(taskId, bidId, null, "TASK_FAILED", message);
        }
    }

    private void executeAiUnit(BidGenerationSnapshot snapshot, BidGenerationUnit unit) {
        List<BidGenerationUnit> units = productionRepository.listGenerationUnits(unit.taskId());
        BidProductionRepository.AiRunHandle run = null;
        TenderAiGateway.AiDiagnostics draftDiagnostics = null;
        long started = System.nanoTime();
        try {
            // 先拿本章所在二级分支的技术域蓝图，再写正文。
            //
            // 蓝图决定同一分支下各章<strong>各写什么、不写什么</strong>。没有它，
            // 每一章都独立地把整个技术域讲一遍，相邻章节大面积重复——
            // 而每一章单独看都合理，这是评审前最难发现的一类质量问题。
            //
            // resolve 按 inputHash 落库，一个分支只生成一次，并行单元和重试都复用；
            // 生成失败就让这个单元失败重试，而不是退回「没有蓝图也写」——
            // 后者会产出正是这套机制要防的那种正文，且没有任何迹象说明它降级了。
            TenderAiGateway.ChapterDraftRequest request = draftFactory.create(
                    snapshot, unit, units, blueprintService.resolve(snapshot, unit));
            String inputHash = BidProductionRules.generationSnapshotHash(
                    snapshot.snapshotHash(), unit.idempotencyKey());
            run = productionRepository.beginAiRun(new BidProductionRepository.AiRunStart(
                    UUID.randomUUID().toString(), unit.bidId(), unit.taskId(), snapshot.id(), unit.id(),
                    "CHAPTER_DRAFT", providerName, modelName, snapshot.promptVersion(),
                    inputHash, unit.idempotencyKey() + ":draft"));
            TenderAiGateway.AiResponse<TenderAiGateway.ChapterDraft> response =
                    tenderAiGateway.draftChapter(request);
            TenderAiGateway.ChapterDraft draft = response.data();
            TenderAiGateway.AiDiagnostics diagnostics = response.diagnostics();
            draftDiagnostics = diagnostics;
            String unitHtml = ensureDraftQuality(snapshot, unit, units, request, draft.html());
            int visibleCharacters = BidContentQualityGuard.visibleCharacterCount(unitHtml);
            double budgetVarianceRatio = budgetVariance(visibleCharacters, unit.wordBudget());
            String budgetStatus = budgetStatus(visibleCharacters, unit.wordBudget());
            String assembled = draftFactory.assembleChapter(units, unit, unitHtml);
            String summary = draftFactory.chapterSummary(units, unit, draft.summary());
            String assembledHash = contentHash(unit, assembled);
            productionRepository.completeGeneratedUnit(new BidProductionRepository.GeneratedUnitCommit(
                    unit.id(), unit.taskId(), unit.bidId(), unit.chapterId(), unit.unitIndex(), unit.unitTitle(),
                    run.id(), run.attemptId(), visibleCharacters, budgetVarianceRatio, budgetStatus,
                    unitHtml, contentHash(unit, unitHtml), draft.summary(), assembled,
                    // 实际应答的模型（Atlas 回显；按路由挂载、故障转移后是兜底模型）。开始时写入的
                    // 配置名只是猜测；没有回显时才退回它。
                    assembledHash, summary, providerName, safe(diagnostics.modelCode(), modelName),
                    snapshot.promptVersion(),
                    elapsedMillis(started), diagnostics.inputTokens(), diagnostics.outputTokens(),
                    diagnostics.reasoningTokens(), diagnostics.cachedInputTokens(),
                    contentHash(unit, unitHtml), diagnostics.finishReason(),
                    diagnostics.responseLength(), diagnostics.responseHash(), diagnostics.attempts(),
                    "blocks,commitments,html,qualityGuard,summary,terms,warnings"));
        } catch (RuntimeException exception) {
            AiGatewayException gatewayFailure = gatewayFailure(exception);
            TenderAiGateway.AiDiagnostics diagnostics = failureDiagnostics(
                    draftDiagnostics, gatewayFailure);
            productionRepository.failGenerationUnit(
                    unit.id(), unit.taskId(), unit.bidId(), unit.chapterId(),
                    run == null ? null : run.id(), run == null ? null : run.attemptId(),
                    errorCode(exception), safe(exception.getMessage(), "正文分段生成失败"),
                    elapsedMillis(started),
                    gatewayFailure == null ? null : gatewayFailure.getFailureReason(),
                    diagnostics.inputTokens(), diagnostics.outputTokens(),
                    diagnostics.reasoningTokens(), diagnostics.cachedInputTokens(),
                    diagnostics.finishReason(), diagnostics.responseLength(),
                    diagnostics.responseHash(), diagnostics.attempts());
            throw exception;
        }
    }

    private TenderAiGateway.AiDiagnostics failureDiagnostics(
            TenderAiGateway.AiDiagnostics response, AiGatewayException failure
    ) {
        if (response != null) {
            return response;
        }
        if (failure == null) {
            return TenderAiGateway.AiDiagnostics.empty();
        }
        return new TenderAiGateway.AiDiagnostics(
                failure.getFinishReason(), failure.getResponseLength(), failure.getResponseHash(),
                failure.getInputTokens(), failure.getOutputTokens(), failure.getReasoningTokens(),
                failure.getCachedInputTokens(), failure.getAttempts());
    }

    private String ensureDraftQuality(
            BidGenerationSnapshot snapshot, BidGenerationUnit unit, List<BidGenerationUnit> units,
            TenderAiGateway.ChapterDraftRequest request, String initialHtml
    ) {
        String html = BidContentQualityGuard.normalizeGeneratedLanguage(
                snapshot.biddingMode(), safe(initialHtml, ""));
        for (int round = 0; round <= MAX_UNIT_REPAIR_ROUNDS; round++) {
            List<BidProductionState.ReviewIssue> blocking = blockingIssues(
                    BidContentQualityGuard.reviewDraft(snapshot, unit, units, html));
            if (blocking.isEmpty()) {
                return html;
            }
            if (round == MAX_UNIT_REPAIR_ROUNDS) {
                throw new BusinessException(
                        "BID_CHAPTER_QUALITY_BLOCKED",
                        "章节即时质检未通过：" + issueSummary(blocking),
                        502);
            }
            TenderAiGateway.RevisionCandidate candidate = aiExecutionService.revise(
                    snapshot.bidId(), unit.taskId(), snapshot.id(), "chapter-unit-quality-repair-v1",
                    new TenderAiGateway.RevisionRequest(
                            unit.idempotencyKey() + "-quality-" + (round + 1),
                            "REWRITE", html,
                            request.previousProse().isBlank()
                                    ? request.previousSummary() : request.previousProse(),
                            request.nextBrief(),
                            BidContentQualityGuard.reviewInstruction(blocking),
                            BidContentQualityGuard.protectedFacts(snapshot, request.criteria()),
                            request.dictionary()));
            if (candidate.html() == null || candidate.html().isBlank()) {
                throw new BusinessException(
                        "BID_CHAPTER_QUALITY_BLOCKED",
                        "章节即时修订未返回有效内容", 502);
            }
            html = BidContentQualityGuard.normalizeGeneratedLanguage(
                    snapshot.biddingMode(), candidate.html());
            productionRepository.appendEvent(unit.taskId(), unit.bidId(), unit.chapterId(),
                    "UNIT_QUALITY_REVISED",
                    "分段正文已根据即时质检自动修订：" + issueSummary(blocking));
        }
        return html;
    }

    private List<BidProductionState.ReviewIssue> blockingIssues(
            List<BidProductionState.ReviewIssue> issues) {
        return issues.stream().filter(issue -> "OPEN".equals(issue.status()))
                .filter(issue -> "ERROR".equals(issue.severity())).toList();
    }

    private String issueSummary(List<BidProductionState.ReviewIssue> issues) {
        String value = issues.stream().limit(3)
                .map(issue -> issue.code() + "：" + issue.message())
                .collect(java.util.stream.Collectors.joining("；"));
        return value.substring(0, Math.min(700, value.length()));
    }

    private BidGenerationSnapshot requireSnapshot(String taskId, String bidId, String ownerId,
                                                   String snapshotId, String snapshotHash) {
        BidGenerationSnapshot snapshot = productionRepository.loadGenerationSnapshot(snapshotId, ownerId);
        if (!snapshot.taskId().equals(taskId) || !snapshot.bidId().equals(bidId)
                || !snapshot.snapshotHash().equals(snapshotHash)) {
            throw new IllegalStateException("生成任务与不可变快照不匹配");
        }
        return snapshot;
    }

    private BidGenerationUnit requireUnit(String taskId, String bidId, String unitId) {
        BidGenerationUnit unit = productionRepository.findGenerationUnit(unitId)
                .orElseThrow(() -> new IllegalStateException("生成单元不存在"));
        if (!unit.taskId().equals(taskId) || !unit.bidId().equals(bidId)) {
            throw new IllegalStateException("生成单元不属于当前任务");
        }
        return unit;
    }

    private BidWorkspace loadWorkspace(String bidId, String ownerId) {
        BidDocument bid = bidRepository.findBidForTask(bidId, ownerId).orElseThrow();
        return bidRepository.loadWorkspace(bid);
    }

    private String contentHash(BidGenerationUnit unit, String content) {
        return BidProductionRules.contentHash(List.of(new BidWorkspace.Chapter(
                unit.chapterId(), "", "", safe(content, ""), "READY", null, 0)));
    }

    private double budgetVariance(int visibleCharacters, int wordBudget) {
        if (wordBudget <= 0) {
            return 0d;
        }
        return (visibleCharacters - wordBudget) / (double) wordBudget;
    }

    private String budgetStatus(int visibleCharacters, int wordBudget) {
        return wordBudget > 0 && visibleCharacters > wordBudget * 1.15d
                ? "OVER_BUDGET" : "WITHIN_BUDGET";
    }

    private String errorCode(RuntimeException exception) {
        return exception instanceof BusinessException business
                ? business.getErrorCode() : "AI_PROVIDER_ERROR";
    }

    private long elapsedMillis(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }

    private String safe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private AiGatewayException gatewayFailure(RuntimeException exception) {
        return exception instanceof AiGatewayException failure ? failure : null;
    }

    public record GenerationLaunch(String taskId, String snapshotId, String snapshotHash) {
    }

    private record PreparedGeneration(
            BidGenerationSnapshot snapshot,
            List<BidGenerationUnit> units
    ) {
    }
}
