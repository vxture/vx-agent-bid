// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
package com.td.czghagent.domain.port;

import java.util.List;
import java.util.Map;

public interface TenderAiGateway {

    Interpretation interpret(InterpretationRequest request);

    default AiResponse<ProjectOverview> extractProjectOverview(InterpretationRequest request) {
        return AiResponse.withoutDiagnostics(
                new ProjectOverview(interpret(request).projectOverview()));
    }

    default AiResponse<TechnicalScoring> extractTechnicalScoring(InterpretationRequest request) {
        return AiResponse.withoutDiagnostics(
                new TechnicalScoring(interpret(request).technicalScoringRequirements()));
    }

    AiResponse<OutlinePlan> planOutline(OutlineRequest request);

    AiResponse<BidStrategy> planOutlineStrategy(OutlineRequest request);

    AiResponse<OutlineSkeletonPlan> planOutlineSkeleton(OutlineSkeletonRequest request);

    AiResponse<OutlineExpansion> expandOutline(OutlineExpansionRequest request);

    OutlinePlan assembleOutline(OutlineAssemblyRequest request);

    AiResponse<BranchBlueprint> planBranchBlueprint(BranchBlueprintRequest request);

    AiResponse<ChapterDraft> draftChapter(ChapterDraftRequest request);

    AiResponse<RevisionCandidate> revise(RevisionRequest request);

    AiResponse<Review> review(ReviewRequest request);

    /**
     * 一次模型调用的诊断。
     *
     * @param modelCode 实际应答的模型（Atlas 回显，故障转移后是兜底模型）；直连或未回显时为 null
     */
    record AiDiagnostics(
            String finishReason,
            Integer responseLength,
            String responseHash,
            Long inputTokens,
            Long outputTokens,
            Long reasoningTokens,
            Long cachedInputTokens,
            Integer attempts,
            String modelCode
    ) {
        public AiDiagnostics(String finishReason, Integer responseLength, String responseHash,
                             Long inputTokens, Long outputTokens, Long reasoningTokens,
                             Long cachedInputTokens, Integer attempts) {
            this(finishReason, responseLength, responseHash, inputTokens, outputTokens,
                    reasoningTokens, cachedInputTokens, attempts, null);
        }

        public static AiDiagnostics empty() {
            return new AiDiagnostics(null, null, null, null, null, null, null, 1);
        }
    }

    record AiResponse<T>(T data, AiDiagnostics diagnostics) {
        public AiResponse {
            diagnostics = diagnostics == null ? AiDiagnostics.empty() : diagnostics;
        }

        public static <T> AiResponse<T> withoutDiagnostics(T data) {
            return new AiResponse<>(data, AiDiagnostics.empty());
        }
    }

    record SourceSegment(String locatorType, String locator, String text) {
    }

    record Criterion(
            String id, String type, String title, String description, Double score,
            String sourceLocator, String sourceExcerpt
    ) {
    }

    record InterpretationRequest(
            String requestId, String documentId, String title, String biddingMode,
            List<SourceSegment> segments
    ) {
    }

    record Interpretation(String projectOverview, String technicalScoringRequirements) {
    }

    record ProjectOverview(String projectOverview) {
    }

    record TechnicalScoring(String technicalScoringRequirements) {
    }

    record ReferenceSummary(String id, String category, String name, String summary) {
    }

    record OutlineRequest(
            String requestId, String title, int targetPages, String biddingMode,
            List<Criterion> criteria, List<ReferenceSummary> references
    ) {
    }

    record TechnicalTheme(
            String title, String objective, String approach, List<String> components,
            List<String> controls, List<String> verification
    ) {
    }

    record ScoringResponseStrategy(
            String requirement, String evaluatorIntent, List<String> responseElements,
            List<String> evidencePlan, int priority
    ) {
    }

    record BidStrategy(
            String projectArchetype, String solutionPositioning,
            List<String> designPrinciples, List<TechnicalTheme> technicalThemes,
            List<ScoringResponseStrategy> scoringResponses,
            List<String> crossCuttingConstraints, List<String> assumptions,
            List<String> prohibitedClaims
    ) {
    }

    record OutlineSkeletonRequest(OutlineRequest outline, BidStrategy strategy) {
    }

    record OutlineSkeletonNode(
            String nodeKey, String parentKey, int level, String title, int plannedPages,
            String taskBrief, List<String> mustKeywords
    ) {
    }

    record OutlineBranchTarget(
            String nodeKey, String rootTitle, String title, String taskBrief,
            List<String> mustKeywords, int preferredLeafCount
    ) {
    }

    record OutlineSkeletonPlan(
            List<OutlineSkeletonNode> nodes, List<String> warnings,
            List<List<OutlineBranchTarget>> batches, List<String> scoringPointIds
    ) {
    }

    record OutlineExpansionRequest(
            OutlineRequest outline, BidStrategy strategy, int batchIndex,
            List<OutlineBranchTarget> branches
    ) {
    }

    record OutlineExpansionNode(
            String parentKey, String title, String taskBrief,
            List<String> mustKeywords, List<String> scoringPointIds
    ) {
    }

    record OutlineExpansion(List<OutlineExpansionNode> nodes, List<String> warnings) {
    }

    record OutlineAssemblyRequest(
            OutlineRequest outline, OutlineSkeletonPlan skeleton,
            List<OutlineExpansion> expansions
    ) {
    }

    record OutlinePlan(
            List<OutlineNode> nodes, List<CoverageItem> coverage,
            FrozenDictionary dictionary, List<String> warnings
    ) {
    }

    record OutlineNode(
            String nodeKey, String parentKey, int level, String title, int plannedPages,
            String taskBrief, List<String> mustKeywords, List<String> scoringPointIds
    ) {
    }

    record CoverageItem(String scoringPointId, List<String> nodeKeys) {
    }

    record FrozenDictionary(List<Metric> metrics, List<Term> terms, List<FixedFact> fixedFacts) {
        public static FrozenDictionary empty() {
            return new FrozenDictionary(List.of(), List.of(), List.of());
        }
    }

    record Metric(String name, String value, String sourceLocator) {
    }

    record Term(String canonical, List<String> forbidden) {
    }

    record FixedFact(String name, String value, String sourceLocator) {
    }

    record ChapterContract(
            String id, String title, int plannedPages, String taskBrief,
            List<String> mustKeywords, List<String> scoringPointIds
    ) {
    }

    record BranchContract(
            String id, String title, String taskBrief, List<String> mustKeywords
    ) {
    }

    record BranchBlueprintRequest(
            String requestId, String bidTitle, String biddingMode,
            String solutionContract, BranchContract branch, List<ChapterContract> chapters,
            List<Criterion> criteria, FrozenDictionary dictionary,
            String writingBible, String termRegistry, String commitmentRegistry
    ) {
    }

    record LeafBlueprint(
            String chapterId, String objective, List<String> technicalDecisions,
            List<String> implementationActions, List<String> deliverables,
            List<String> validationMethods, String presentation
    ) {
    }

    record BranchBlueprint(
            String solutionPositioning, List<String> sharedDecisions,
            List<String> sharedConstraints, List<LeafBlueprint> chapters,
            List<String> assumptions, List<String> prohibitedClaims
    ) {
    }

    record ChapterDraftRequest(
            String requestId, String bidTitle, String biddingMode, ChapterContract chapter,
            BranchBlueprint branchBlueprint,
            List<Criterion> criteria, FrozenDictionary dictionary, List<SourceSegment> evidence,
            String writingPlan, String styleProfile, String previousSummary,
            String previousProse, String chapterOpening, String recentTableCaption,
            List<String> repetitionAvoidance, String nextBrief, int wordBudget,
            int unitIndex, int unitCount, String unitTitle,
            String writingBible, String termRegistry, String commitmentRegistry
    ) {
    }

    record ChapterDraft(
            List<ContentBlock> blocks, String summary, List<DraftTerm> terms,
            List<Commitment> commitments, List<String> warnings, String html
    ) {
    }

    record ContentBlock(
            String type, Integer level, String text, List<String> items, String caption,
            String note, List<String> header, List<List<String>> rows, List<String> sourceRefs
    ) {
    }

    record DraftTerm(String term, String definition) {
    }

    record Commitment(String text, String sourceRef) {
    }

    record RevisionRequest(
            String requestId, String mode, String selectedHtml, String beforeContext,
            String afterContext, String instruction, List<String> protectedFacts,
            FrozenDictionary dictionary
    ) {
    }

    record RevisionCandidate(
            List<ContentBlock> blocks, String changeSummary, List<String> preservedFacts,
            List<String> warnings, String html
    ) {
    }

    record ReviewRequest(String requestId, Map<String, Object> payload) {
    }

    record Review(
            boolean passed, List<ReviewIssue> issues, ReviewCoverage coverage,
            List<String> warnings, String reviewSummary
    ) {
    }

    record ReviewIssue(
            String severity, String code, String chapterId, String message,
            String suggestion, List<String> sourceRefs
    ) {
    }

    record ReviewCoverage(int total, int covered, List<String> missingScoringPointIds) {
    }
}
