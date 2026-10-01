// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-04
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.exception.AiGatewayException;
import com.td.czghagent.domain.model.BidProductionRules;
import com.td.czghagent.domain.port.TenderAiGateway;
import com.td.czghagent.domain.repository.BidProductionRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Locale;
import java.util.UUID;
import java.util.function.Supplier;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Service
public class BidAiExecutionService {
    private final TenderAiGateway gateway;
    private final BidProductionRepository repository;
    private final String providerName;
    private final String fastModelName;
    private final String qualityModelName;
    private final AiInputFingerprint fingerprint = new AiInputFingerprint();

    public BidAiExecutionService(
            TenderAiGateway gateway,
            BidProductionRepository repository,
            @Value("${app.ai.provider-name:AUTO}") String providerName,
            @Value("${app.ai.fast-model-name:deepseek-v4-flash}") String fastModelName,
            @Value("${app.ai.quality-model-name:deepseek-v4-pro}") String qualityModelName
    ) {
        this.gateway = gateway;
        this.repository = repository;
        this.providerName = normalizeProvider(providerName);
        this.fastModelName = fastModelName;
        this.qualityModelName = qualityModelName;
    }

    public TenderAiGateway.Interpretation interpret(
            String bidId, TenderAiGateway.InterpretationRequest request
    ) {
        return execute(bidId, null, null, "INTERPRETATION", "interpretation-v1",
                fastModelName, "招标文件解读", request,
                () -> TenderAiGateway.AiResponse.withoutDiagnostics(gateway.interpret(request)));
    }

    public TenderAiGateway.ProjectOverview extractProjectOverview(
            String bidId, TenderAiGateway.InterpretationRequest request
    ) {
        return execute(bidId, null, null, "INTERPRETATION_PROJECT_OVERVIEW",
                "interpretation-project-overview-v4", fastModelName, "项目概述", request,
                () -> gateway.extractProjectOverview(request));
    }

    public TenderAiGateway.TechnicalScoring extractTechnicalScoring(
            String bidId, TenderAiGateway.InterpretationRequest request
    ) {
        return execute(bidId, null, null, "INTERPRETATION_TECHNICAL_SCORING",
                "interpretation-technical-scoring-v4", fastModelName, "技术部分评分要求", request,
                () -> gateway.extractTechnicalScoring(request));
    }

    public TenderAiGateway.OutlinePlan planOutline(
            String bidId, TenderAiGateway.OutlineRequest request
    ) {
        return execute(bidId, null, null, "OUTLINE", "outline-strategy-v5",
                qualityModelName, "技术标目录", request, () -> gateway.planOutline(request));
    }

    public TenderAiGateway.BidStrategy planOutlineStrategy(
            String bidId, TenderAiGateway.OutlineRequest request
    ) {
        return execute(bidId, null, null, "OUTLINE_STRATEGY", "bid-strategy-v2",
                qualityModelName, "技术标投标响应策略", request,
                () -> gateway.planOutlineStrategy(request));
    }

    public TenderAiGateway.OutlineSkeletonPlan planOutlineSkeleton(
            String bidId, TenderAiGateway.OutlineSkeletonRequest request
    ) {
        return execute(bidId, null, null, "OUTLINE_SKELETON", "outline-skeleton-v3",
                qualityModelName, "技术标一二级目录骨架", request,
                () -> gateway.planOutlineSkeleton(request));
    }

    public TenderAiGateway.OutlineExpansion expandOutline(
            String bidId, TenderAiGateway.OutlineExpansionRequest request
    ) {
        return execute(bidId, null, null, "OUTLINE_EXPANSION", "outline-expansion-v3",
                fastModelName, "技术标三级目录批次", request,
                () -> gateway.expandOutline(request));
    }

    public TenderAiGateway.OutlinePlan assembleOutline(
            TenderAiGateway.OutlineAssemblyRequest request
    ) {
        return gateway.assembleOutline(request);
    }

    public TenderAiGateway.BranchBlueprint planBranchBlueprint(
            String bidId, String taskId, String snapshotId, String promptVersion,
            TenderAiGateway.BranchBlueprintRequest request) {
        return execute(bidId, taskId, snapshotId, "BRANCH_BLUEPRINT", promptVersion,
                qualityModelName, "二级技术域蓝图", request,
                () -> gateway.planBranchBlueprint(request));
    }

    public TenderAiGateway.RevisionCandidate revise(
            String bidId, TenderAiGateway.RevisionRequest request
    ) {
        return revise(bidId, null, null, "revision-v1", request);
    }

    public TenderAiGateway.RevisionCandidate revise(
            String bidId, String taskId, String snapshotId, String promptVersion,
            TenderAiGateway.RevisionRequest request
    ) {
        return execute(bidId, taskId, snapshotId, "REVISION", promptVersion,
                qualityModelName, "局部改写内容", request, () -> gateway.revise(request));
    }

    public TenderAiGateway.Review review(
            String bidId, String taskId, String snapshotId, String promptVersion,
            TenderAiGateway.ReviewRequest request
    ) {
        return execute(bidId, taskId, snapshotId, "REVIEW", promptVersion,
                qualityModelName, "成稿审查结果", request, () -> gateway.review(request));
    }

    String providerName() {
        return providerName;
    }

    String modelName() {
        return qualityModelName;
    }

    String fastModelName() {
        return fastModelName;
    }

    private <T> T execute(
            String bidId, String taskId, String snapshotId, String operation,
            String promptVersion, String modelName, String objectName, Object input,
            Supplier<TenderAiGateway.AiResponse<T>> invocation
    ) {
        String inputHash = fingerprint.hash(input, promptVersion);
        BidProductionRepository.AiRunHandle run = repository.beginAiRun(
                new BidProductionRepository.AiRunStart(
                        UUID.randomUUID().toString(), bidId, taskId, snapshotId, null,
                        operation, providerName, modelName, promptVersion, inputHash,
                        bidId + ":" + operation + ":" + inputHash,
                        objectName, promptVersion));
        long started = System.nanoTime();
        TenderAiGateway.AiDiagnostics responseDiagnostics = null;
        try {
            TenderAiGateway.AiResponse<T> response = invocation.get();
            if (response == null || response.data() == null) {
                throw new BusinessException("AI_OUTPUT_INVALID", "AI 服务未返回有效结果", 502);
            }
            T output = response.data();
            TenderAiGateway.AiDiagnostics diagnostics = response.diagnostics();
            responseDiagnostics = diagnostics;
            repository.completeAiRun(
                    run.id(), run.attemptId(), elapsedMillis(started), diagnostics.inputTokens(),
                    diagnostics.outputTokens(), diagnostics.reasoningTokens(),
                    diagnostics.cachedInputTokens(), fingerprint.hash(output, promptVersion),
                    responseFields(output), diagnostics.finishReason(),
                    diagnostics.responseLength(), diagnostics.responseHash(),
                    diagnostics.attempts(), diagnostics.modelCode());
            return output;
        } catch (RuntimeException exception) {
            AiGatewayException gatewayFailure = gatewayFailure(exception);
            TenderAiGateway.AiDiagnostics diagnostics = failureDiagnostics(
                    responseDiagnostics, gatewayFailure);
            repository.failAiRun(
                    run.id(), run.attemptId(), elapsedMillis(started),
                    diagnostics.inputTokens(), diagnostics.outputTokens(),
                    diagnostics.reasoningTokens(), diagnostics.cachedInputTokens(),
                    errorCode(exception), safeMessage(exception),
                    failureDiagnostic(gatewayFailure),
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

    String inputHash(Object value, String promptVersion) {
        return fingerprint.hash(value, promptVersion);
    }

    private String failureDiagnostic(AiGatewayException failure) {
        if (failure == null) {
            return null;
        }
        String detail = failure.getFailureReason() == null ? "" : failure.getFailureReason();
        String stage = failure.getStage() == null ? "" : failure.getStage();
        String elapsed = failure.getElapsedMillis() == null
                ? "" : String.valueOf(failure.getElapsedMillis());
        return "stage=" + stage + ";elapsedMillis=" + elapsed + ";detail=" + detail;
    }

    private String responseFields(Object output) {
        if (output == null || !output.getClass().isRecord()) {
            return "";
        }
        return Stream.of(output.getClass().getRecordComponents())
                .map(component -> component.getName())
                .sorted()
                .collect(Collectors.joining(","));
    }

    private long elapsedMillis(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }

    private String errorCode(RuntimeException exception) {
        return exception instanceof BusinessException business
                ? business.getErrorCode() : "AI_PROVIDER_ERROR";
    }

    private String safeMessage(RuntimeException exception) {
        String message = exception.getMessage();
        String safe = message == null || message.isBlank() ? "AI调用失败" : message;
        safe = safe.replaceAll("(?i)(bearer|api[-_ ]?key)\\s*[:=]?\\s*[^\\s,;]+", "$1 [FILTERED]");
        return safe.substring(0, Math.min(1000, safe.length()));
    }

    private AiGatewayException gatewayFailure(RuntimeException exception) {
        return exception instanceof AiGatewayException failure ? failure : null;
    }

    static String normalizeProvider(String value) {
        String normalized = value == null ? "UNKNOWN" : value.trim().toUpperCase(Locale.ROOT);
        return switch (normalized) {
            case "DEEPSEEK", "DIRECT_DEEPSEEK" -> "DIRECT_DEEPSEEK";
            case "BAILIAN_DEEPSEEK", "DASHSCOPE_DEEPSEEK", "QWEN_DEEPSEEK" -> "DASHSCOPE_DEEPSEEK";
            case "QWEN", "DIRECT_QWEN" -> "DIRECT_QWEN";
            default -> "UNKNOWN";
        };
    }
}
