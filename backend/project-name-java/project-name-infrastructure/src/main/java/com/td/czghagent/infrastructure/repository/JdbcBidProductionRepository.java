package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.model.BidGenerationSnapshot;
import com.td.czghagent.domain.model.BidGenerationUnit;
import com.td.czghagent.domain.model.BidProductionState;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.repository.BidProductionRepository;
import com.td.czghagent.domain.port.TenderAiGateway;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/** Production-state adapter coordinating snapshot, unit, review and lifecycle persistence. */
@Repository
public class JdbcBidProductionRepository implements BidProductionRepository {
    private final JdbcGenerationSnapshotPersistence snapshots;
    private final JdbcGenerationUnitPersistence units;
    private final JdbcBidReviewPersistence reviews;
    private final JdbcBidLifecyclePersistence lifecycle;

    public JdbcBidProductionRepository(JdbcTemplate jdbcTemplate,
                                       JdbcGenerationSnapshotPersistence snapshots,
                                       JdbcGenerationUnitPersistence units) {
        this.snapshots = snapshots;
        this.units = units;
        this.reviews = new JdbcBidReviewPersistence(jdbcTemplate);
        this.lifecycle = new JdbcBidLifecyclePersistence(jdbcTemplate);
    }

    @Override
    public BidProductionState loadState(String bidId, String latestTaskId) {
        return reviews.loadState(bidId, latestTaskId);
    }

    @Override
    @Transactional
    public String freezeInterpretation(String bidId, String userId, String contentHash,
                                       List<BidWorkspace.Criterion> criteria,
                                       List<BidProductionState.FrozenFact> facts) {
        return reviews.freezeInterpretation(bidId, userId, contentHash, criteria, facts);
    }

    @Override
    public void markInterpretationReview(String bidId, String staleReason) {
        reviews.markInterpretationReview(bidId, staleReason);
    }

    @Override
    public void freezeOutline(String bidId, String contentHash) {
        reviews.freezeOutline(bidId, contentHash);
    }

    @Override
    public void markOutlineReview(String bidId, String staleReason) {
        reviews.markOutlineReview(bidId, staleReason);
    }

    @Override
    public String createGenerationSnapshot(
            String taskId, String ownerId, BidWorkspace workspace, String snapshotHash,
            String solutionContract, String writingBible, String termRegistry, String commitmentRegistry,
            String promptVersion, List<BidReferenceChunk> referenceChunks,
            List<GenerationUnitPlan> units) {
        return snapshots.create(
                taskId, ownerId, workspace, snapshotHash, solutionContract, writingBible, termRegistry,
                commitmentRegistry, promptVersion, referenceChunks, units);
    }

    @Override
    public BidGenerationSnapshot loadGenerationSnapshot(String snapshotId, String ownerId) {
        return snapshots.load(snapshotId, ownerId);
    }

    @Override
    public Optional<TenderAiGateway.BranchBlueprint> findBranchBlueprint(
            String snapshotId, String branchOutlineId, String inputHash) {
        return snapshots.findBranchBlueprint(snapshotId, branchOutlineId, inputHash);
    }

    @Override
    public void saveBranchBlueprint(
            String snapshotId, String branchOutlineId, String inputHash,
            TenderAiGateway.BranchBlueprint blueprint, String outputHash, String promptVersion) {
        snapshots.saveBranchBlueprint(
                snapshotId, branchOutlineId, inputHash, blueprint, outputHash, promptVersion);
    }

    @Override
    public List<BidGenerationUnit> listGenerationUnits(String taskId) {
        return units.list(taskId);
    }

    @Override
    public Optional<BidGenerationUnit> findGenerationUnit(String unitId) {
        return units.find(unitId);
    }

    @Override
    public boolean startGenerationUnit(String unitId) {
        return units.start(unitId);
    }

    @Override
    public AiRunHandle beginAiRun(AiRunStart run) {
        return units.begin(run);
    }

    @Override
    public void completeAiRun(String aiRunId, String aiRunAttemptId,
                              long durationMillis, Long inputTokens,
                              Long outputTokens, Long reasoningTokens, Long cachedInputTokens,
                              String outputHash, String responseFields,
                              String finishReason, Integer responseLength, String responseHash,
                              Integer attempts, String modelCode) {
        units.completeRun(aiRunId, aiRunAttemptId, durationMillis, inputTokens, outputTokens,
                reasoningTokens, cachedInputTokens,
                outputHash, responseFields, finishReason, responseLength, responseHash, attempts,
                modelCode);
    }

    @Override
    public void failAiRun(String aiRunId, String aiRunAttemptId, long durationMillis,
                          Long inputTokens, Long outputTokens,
                          Long reasoningTokens, Long cachedInputTokens,
                          String errorCode, String errorMessage, String failureReason,
                          String finishReason, Integer responseLength, String responseHash,
                          Integer attempts) {
        units.failRun(aiRunId, aiRunAttemptId, durationMillis,
                inputTokens, outputTokens, reasoningTokens, cachedInputTokens,
                errorCode, errorMessage, failureReason,
                finishReason, responseLength, responseHash, attempts);
    }

    @Override
    public void completeGeneratedUnit(GeneratedUnitCommit commit) {
        units.complete(commit);
    }

    @Override
    public void skipGenerationUnit(String unitId, String taskId, String bidId,
                                   String chapterId, String summary) {
        units.skip(unitId, taskId, bidId, chapterId, summary);
    }

    @Override
    public void failGenerationUnit(String unitId, String taskId, String bidId,
                                   String chapterId, String aiRunId, String aiRunAttemptId,
                                   String errorCode,
                                   String errorMessage, long durationMillis, String failureReason,
                                   Long inputTokens, Long outputTokens,
                                   Long reasoningTokens, Long cachedInputTokens,
                                   String finishReason, Integer responseLength, String responseHash,
                                   Integer attempts) {
        units.fail(unitId, taskId, bidId, chapterId, aiRunId, aiRunAttemptId,
                errorCode, errorMessage, durationMillis, failureReason,
                inputTokens, outputTokens, reasoningTokens, cachedInputTokens, finishReason,
                responseLength, responseHash, attempts);
    }

    @Override
    public void assignWorkflowRun(String taskId, String workflowRunId, String snapshotHash) {
        lifecycle.assignWorkflowRun(taskId, workflowRunId, snapshotHash);
    }

    @Override
    @Transactional
    public void startUnit(String taskId, String bidId, String chapterId) {
        lifecycle.startUnit(taskId, chapterId);
    }

    @Override
    @Transactional
    public void completeUnit(String taskId, String bidId, String chapterId, String summary) {
        lifecycle.completeUnit(taskId, chapterId, summary);
    }

    @Override
    @Transactional
    public void failUnit(String taskId, String bidId, String chapterId, String errorMessage) {
        lifecycle.failUnit(taskId, chapterId, errorMessage);
    }

    @Override
    public void appendEvent(String taskId, String bidId, String chapterId,
                            String eventType, String message) {
        lifecycle.appendEvent(taskId, bidId, chapterId, eventType, message);
    }

    @Override
    @Transactional
    public void saveChapterVersion(String bidId, String chapterId, String sourceType,
                                   String content, String contentHash, String summary, String userId) {
        lifecycle.saveChapterVersion(
                bidId, chapterId, sourceType, content, contentHash, summary, userId);
    }

    @Override
    @Transactional
    public boolean applyReviewedChapter(String bidId, String chapterId,
                                        long revision, String content) {
        return lifecycle.applyReviewedChapter(bidId, chapterId, revision, content);
    }

    @Override
    @Transactional
    public boolean applyCompactedChapter(
            String taskId, String bidId, String chapterId, long revision,
            String content, String contentHash, String summary, String userId
    ) {
        if (!lifecycle.applyReviewedChapter(bidId, chapterId, revision, content)) {
            return false;
        }
        lifecycle.saveChapterVersion(
                bidId, chapterId, "BUDGET_COMPACTION", content, contentHash, summary, userId);
        units.markChapterCompacted(taskId, chapterId);
        return true;
    }

    @Override
    @Transactional
    public void replaceReviewIssues(String bidId, List<BidProductionState.ReviewIssue> issues) {
        reviews.replaceReviewIssues(bidId, issues);
    }

    @Override
    public void markContentReview(String bidId, String staleReason) {
        reviews.markContentReview(bidId, staleReason);
    }

    @Override
    public void freezeContent(String bidId, String contentHash) {
        reviews.freezeContent(bidId, contentHash);
    }

    @Override
    @Transactional
    public String createLayoutJob(String bidId, String userId,
                                  String inputHash, int targetPages) {
        return lifecycle.createLayoutJob(bidId, userId, inputHash, targetPages);
    }

    @Override
    public void assignLayoutWorkflow(String layoutJobId, String bidId, String workflowRunId) {
        lifecycle.assignLayoutWorkflow(layoutJobId, bidId, workflowRunId);
    }

    @Override
    @Transactional
    public void startLayoutJob(String layoutJobId, String bidId) {
        lifecycle.startLayoutJob(layoutJobId, bidId);
    }

    @Override
    @Transactional
    public void completeLayoutJob(String layoutJobId, String bidId, Integer actualPages,
                                  String qaStatus, String qaSummary) {
        lifecycle.completeLayoutJob(layoutJobId, bidId, actualPages, qaStatus, qaSummary);
    }

    @Override
    @Transactional
    public void failLayoutJob(String layoutJobId, String bidId, String errorMessage) {
        lifecycle.failLayoutJob(layoutJobId, bidId, errorMessage);
    }
}
