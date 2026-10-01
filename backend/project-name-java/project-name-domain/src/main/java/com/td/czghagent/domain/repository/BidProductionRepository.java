// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-28
package com.td.czghagent.domain.repository;

import com.td.czghagent.domain.model.BidProductionState;
import com.td.czghagent.domain.model.BidGenerationSnapshot;
import com.td.czghagent.domain.model.BidGenerationUnit;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.port.TenderAiGateway;

import java.util.List;
import java.util.Optional;

public interface BidProductionRepository {
    BidProductionState loadState(String bidId, String latestTaskId);

    String freezeInterpretation(String bidId, String userId, String contentHash,
                                List<BidWorkspace.Criterion> criteria,
                                List<BidProductionState.FrozenFact> facts);

    void markInterpretationReview(String bidId, String staleReason);

    void freezeOutline(String bidId, String contentHash);

    void markOutlineReview(String bidId, String staleReason);

    String createGenerationSnapshot(
            String taskId,
            String ownerId,
            BidWorkspace workspace,
            String snapshotHash,
            String solutionContract,
            String writingBible,
            String termRegistry,
            String commitmentRegistry,
            String promptVersion,
            List<BidReferenceChunk> referenceChunks,
            List<GenerationUnitPlan> units
    );

    BidGenerationSnapshot loadGenerationSnapshot(String snapshotId, String ownerId);

    Optional<TenderAiGateway.BranchBlueprint> findBranchBlueprint(
            String snapshotId, String branchOutlineId, String inputHash);

    void saveBranchBlueprint(
            String snapshotId, String branchOutlineId, String inputHash,
            TenderAiGateway.BranchBlueprint blueprint, String outputHash, String promptVersion);

    List<BidGenerationUnit> listGenerationUnits(String taskId);

    Optional<BidGenerationUnit> findGenerationUnit(String unitId);

    boolean startGenerationUnit(String unitId);

    AiRunHandle beginAiRun(AiRunStart run);

    void completeAiRun(String aiRunId, String aiRunAttemptId,
                       long durationMillis, Long inputTokens,
                       Long outputTokens, Long reasoningTokens, Long cachedInputTokens,
                       String outputHash, String responseFields,
                       String finishReason, Integer responseLength, String responseHash,
                       Integer attempts, String modelCode);

    void failAiRun(String aiRunId, String aiRunAttemptId,
                   long durationMillis, Long inputTokens, Long outputTokens,
                   Long reasoningTokens, Long cachedInputTokens,
                   String errorCode, String errorMessage,
                   String failureReason, String finishReason, Integer responseLength,
                   String responseHash, Integer attempts);

    void completeGeneratedUnit(GeneratedUnitCommit commit);

    void skipGenerationUnit(String unitId, String taskId, String bidId,
                            String chapterId, String summary);

    void failGenerationUnit(String unitId, String taskId, String bidId,
                            String chapterId, String aiRunId, String aiRunAttemptId,
                            String errorCode,
                            String errorMessage, long durationMillis, String failureReason,
                            Long inputTokens, Long outputTokens,
                            Long reasoningTokens, Long cachedInputTokens,
                            String finishReason, Integer responseLength, String responseHash,
                            Integer attempts);

    void assignWorkflowRun(String taskId, String workflowRunId, String snapshotHash);

    void startUnit(String taskId, String bidId, String chapterId);

    void completeUnit(String taskId, String bidId, String chapterId, String summary);

    void failUnit(String taskId, String bidId, String chapterId, String errorMessage);

    void appendEvent(String taskId, String bidId, String chapterId,
                     String eventType, String message);

    void saveChapterVersion(String bidId, String chapterId, String sourceType,
                            String content, String contentHash, String summary, String userId);

    boolean applyReviewedChapter(String bidId, String chapterId, long revision, String content);

    boolean applyCompactedChapter(
            String taskId, String bidId, String chapterId, long revision,
            String content, String contentHash, String summary, String userId);

    void replaceReviewIssues(String bidId, List<BidProductionState.ReviewIssue> issues);

    void markContentReview(String bidId, String staleReason);

    void freezeContent(String bidId, String contentHash);

    String createLayoutJob(String bidId, String userId, String inputHash, int targetPages);

    void assignLayoutWorkflow(String layoutJobId, String bidId, String workflowRunId);

    void startLayoutJob(String layoutJobId, String bidId);

    void completeLayoutJob(String layoutJobId, String bidId, Integer actualPages,
                           String qaStatus, String qaSummary);

    void failLayoutJob(String layoutJobId, String bidId, String errorMessage);

    record GenerationUnitPlan(
            String id,
            String chapterId,
            int unitIndex,
            String unitTitle,
            int wordBudget,
            String idempotencyKey
    ) {
    }

    record AiRunStart(
            String id,
            String bidId,
            String taskId,
            String snapshotId,
            String generationUnitId,
            String operationType,
            String provider,
            String modelName,
            String promptVersion,
            String inputSnapshotHash,
            String idempotencyKey,
            String objectName,
            String schemaVersion
    ) {
        public AiRunStart(
                String id, String bidId, String taskId, String snapshotId,
                String generationUnitId, String operationType, String provider,
                String modelName, String promptVersion, String inputSnapshotHash,
                String idempotencyKey
        ) {
            this(id, bidId, taskId, snapshotId, generationUnitId, operationType,
                    provider, modelName, promptVersion, inputSnapshotHash, idempotencyKey,
                    operationType, promptVersion);
        }
    }

    record AiRunHandle(String id, String attemptId, String status, int attemptCount) {
    }

    record GeneratedUnitCommit(
            String unitId,
            String taskId,
            String bidId,
            String chapterId,
            int unitIndex,
            String unitTitle,
            String aiRunId,
            String aiRunAttemptId,
            int visibleCharacters,
            double budgetVarianceRatio,
            String budgetStatus,
            String unitContent,
            String unitContentHash,
            String unitSummary,
            String assembledChapterContent,
            String assembledChapterHash,
            String chapterSummary,
            String provider,
            String modelName,
            String promptVersion,
            long durationMillis,
            Long inputTokens,
            Long outputTokens,
            Long reasoningTokens,
            Long cachedInputTokens,
            String outputHash,
            String finishReason,
            Integer responseLength,
            String responseHash,
            Integer attempts,
            String responseFields
    ) {
    }
}
