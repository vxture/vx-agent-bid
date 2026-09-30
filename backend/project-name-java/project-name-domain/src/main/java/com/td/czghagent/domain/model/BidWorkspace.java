// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
package com.td.czghagent.domain.model;

import java.time.LocalDateTime;
import java.util.List;

public record BidWorkspace(
        BidDocument bid,
        SourceFile sourceFile,
        List<Criterion> criteria,
        List<OutlineNode> outline,
        List<Chapter> chapters,
        OutlineTask outlineTask,
        GenerationTask generationTask,
        List<String> selectedAssetIds,
        List<BidExport> exports,
        BidProductionState production
) {
    public record SourceFile(
            String id, String originalFileName, String mediaType, long fileSize,
            String parseStatus, String parseStage, int parseProgress, String errorMessage,
            String overviewStatus, String overviewErrorMessage,
            String scoringStatus, String scoringErrorMessage,
            LocalDateTime uploadedAt, LocalDateTime parseStartedAt, LocalDateTime parseFinishedAt
    ) {
    }

    public record Criterion(
            String id, String type, String title, String description, Double score,
            String sourceExcerpt, String sourceLocator, String scope, String confidence,
            int sortOrder, boolean manuallyEdited
    ) {
        public Criterion(String id, String type, String title, String description, Double score,
                         String sourceExcerpt, int sortOrder, boolean manuallyEdited) {
            this(id, type, title, description, score, sourceExcerpt, "", "TECHNICAL", "HIGH",
                    sortOrder, manuallyEdited);
        }
    }

    public record OutlineNode(
            String id, String parentId, int level, String title, int plannedPages,
            int sortOrder, long revision, String taskBrief, List<String> mustKeywords,
            List<String> scoringPointIds
    ) {
        public OutlineNode(String id, String parentId, int level, String title, int plannedPages,
                           int sortOrder, long revision) {
            this(id, parentId, level, title, plannedPages, sortOrder, revision, "", List.of(), List.of());
        }
    }

    public record Chapter(
            String id, String outlineNodeId, String title, String content,
            String generationStatus, LocalDateTime updatedAt, long revision
    ) {
    }

    public record GenerationTask(
            String id, String status, int totalUnits, int completedUnits,
            String errorMessage, LocalDateTime createdAt, LocalDateTime finishedAt
    ) {
        public int progress() {
            return totalUnits == 0 ? 0 : Math.min(100, completedUnits * 100 / totalUnits);
        }
    }

    /**
     * 目录生成任务。
     *
     * @param warnings 目录生成的提示：规模与篇幅估算的偏差、略去的空章节。只提示，不代表失败——
     *                 目录照常可用，由用户决定直接用、编辑还是重新生成。永不为 null。
     */
    public record OutlineTask(
            String id, String status, String stage, int progress, long inputRevision,
            String workflowRunId, String errorMessage, LocalDateTime createdAt,
            LocalDateTime startedAt, LocalDateTime finishedAt, List<String> warnings
    ) {
        public OutlineTask {
            warnings = warnings == null ? List.of() : List.copyOf(warnings);
        }
    }
}
