// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
package com.td.czghagent.domain.repository;

import com.td.czghagent.domain.model.BidDocument;
import com.td.czghagent.domain.model.BidExport;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidReferenceAsset;
import com.td.czghagent.domain.model.BidSummary;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.model.BidWorkspaceViews;
import com.td.czghagent.domain.model.PageCursor;

import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;

public interface BidRepository {
    void insertBid(BidDocument bid);

    /**
     * 当前用户在当前工作空间里的标书。
     *
     * <p>归属人与工作空间<strong>两个条件都要</strong>：同一个平台用户可以属于多个工作空间，
     * 只按归属人过滤会让 A 空间的标书出现在 B 空间里——而那个响应看起来完全正常。
     *
     * <p>键集分页（通则 A-3）：按 {@code (updatedAt, id)} 降序，{@code after} 为空表示从头开始，
     * 取 {@code limit} 行——调用方多取一条来判断还有没有下一页。{@code id} 是并列时的决胜键，
     * 缺了它，同一时刻更新的几份标书会在翻页时重复或漏掉。
     * 锚点时间取的是 {@code updatedAt}：翻页途中被编辑的标书可能跨页移动，这是保留
     * 「最近更新在前」这个排序所接受的代价。
     */
    List<BidSummary> listBids(String ownerId, TenantScope tenant, PageCursor after, int limit);

    /** 请求路径的归属校验：归属人 + 工作空间。见 {@link #listBids}。 */
    Optional<BidDocument> findBid(String bidId, String ownerId, TenantScope tenant);

    /**
     * <strong>只给后台任务用</strong>：按归属人取标书，不看工作空间。
     *
     * <p>Temporal 活动拿到的 bidId 来自一个已经在请求路径上通过了归属与租户校验的任务，
     * 而它必须先取到标书才知道租户轴（租户轴以标书行为准）。请求路径不得调用它——
     * 那会绕过工作空间隔离，而且不报任何错。
     */
    Optional<BidDocument> findBidForTask(String bidId, String ownerId);

    boolean existsBid(String bidId);

    BidWorkspace loadWorkspace(BidDocument bid);

    BidWorkspaceViews.Metadata loadMetadata(BidDocument bid);

    BidWorkspaceViews.OutlineView loadOutline(String bidId);

    Optional<BidWorkspaceViews.ChapterDetail> findChapterDetail(String bidId, String chapterId);

    BidWorkspaceViews.GenerationProgress loadGenerationProgress(String bidId);

    boolean updateSetup(String bidId, String title, int targetPages, String biddingMode, long revision);

    void insertSourceFile(SourceFileRecord source);

    Optional<SourceFileRecord> findSourceFile(String bidId);

    boolean beginSourceParse(String sourceId, String bidId);

    boolean updateSourceParseProgress(String sourceId, String stage, int progress);

    boolean saveParsedSource(String sourceId, String bidId, String extractedText,
                             List<SourceSegmentRecord> segments);

    List<SourceSegmentRecord> listSourceSegments(String sourceId);

    boolean beginInterpretationObject(String sourceId, String objectType);

    boolean completeInterpretationObject(String sourceId, String bidId, String objectType,
                                         String content, BidWorkspace.Criterion criterion);

    boolean failInterpretationObject(String sourceId, String objectType, String errorMessage);

    boolean completeSourceParse(String sourceId, String bidId);

    boolean failSourceParse(String sourceId, String bidId, String errorMessage);

    void replaceCriteria(String bidId, List<BidWorkspace.Criterion> criteria, boolean manual);

    void replaceAssetSelections(String bidId, String ownerId, TenantScope tenant, List<String> assetIds);

    void replaceOutline(String bidId, List<BidWorkspace.OutlineNode> nodes, boolean confirmed);

    void confirmOutline(String bidId);

    String createOutlineTask(String bidId);

    void assignOutlineWorkflowRun(String taskId, String workflowRunId);

    boolean updateOutlineTaskProgress(String taskId, String stage, int progress);

    /**
     * 保存生成的目录并完成任务。
     *
     * @param warnings AI 服务给出的目录提示（规模偏差等），随任务保存供页面显示
     */
    boolean completeOutlineTask(String taskId, String bidId,
                                List<BidWorkspace.OutlineNode> nodes, List<String> warnings);

    boolean failOutlineTask(String taskId, String bidId, String errorMessage);

    String createGenerationTask(String bidId, int totalUnits);

    void startGenerationTask(String taskId);

    boolean saveGeneratedChapter(String chapterId, String content);

    void advanceGenerationTask(String taskId);

    boolean completeGenerationTask(String taskId, String bidId);

    boolean failGenerationTask(String taskId, String bidId, String message);

    GenerationTaskExecution pauseGenerationTask(String bidId);

    GenerationTaskExecution resumeGenerationTask(String bidId);

    boolean updateChapter(String bidId, String chapterId, String content, long revision);

    void markContentStale(String bidId);

    void insertAsset(AssetRecord asset);

    /** 键集分页，按 {@code (updatedAt, id)} 降序；约定同 {@link #listBids}。 */
    List<BidReferenceAsset> listAssets(String ownerId, TenantScope tenant, String category, String keyword,
                                       PageCursor after, int limit);

    /** 按标识取一个可用素材——上传后回显用，不必为找一条去翻整张表。 */
    Optional<BidReferenceAsset> findActiveAsset(String assetId, String ownerId, TenantScope tenant);

    Optional<AssetRecord> findAsset(String assetId, String ownerId, TenantScope tenant);

    void replaceAssetChunks(String assetId, List<BidReferenceChunk> chunks);

    List<BidReferenceChunk> listAssetChunks(List<String> assetIds);

    void markAssetIngestion(String assetId, String status, String errorMessage);

    boolean removeAsset(String assetId, String ownerId, TenantScope tenant);

    int nextExportVersion(String bidId);

    void insertExport(ExportRecord export);

    /**
     * 把这份标书的字数统计高水位抬到 {@code characters}。
     *
     * <p>抬了，返回抬之前的值；没有超过现有水位，返回空、什么都不写。
     * 判断与写入必须原子——两次导出并发时，后到的那个要读到被抬过的水位，
     * 否则两边各报一遍重叠的那一段。不动 {@code revision}：计量不是用户可见的修改。
     */
    OptionalLong raiseMeteredCharacters(String bidId, long characters);

    /**
     * 一份标书的成果导出，键集分页，按 {@code (createdAt, id)} 降序——第一条就是最近生成的那份。
     * 约定同 {@link #listBids}。
     */
    List<BidExport> listExports(String bidId, PageCursor after, int limit);

    /** 按标识取一次导出的对外视图——创建后回显用。 */
    Optional<BidExport> findExportSummary(String bidId, String exportId);

    /**
     * 按标识取一次成果导出。
     *
     * <p>与 {@code findLatestExport} 并存而不是取代它：前者回答「这一个」，后者回答「最近那个」。
     * 下载路由用前者，因为「最新」是一个视角而不是一个资源标识，
     * 把它写进路径段会让资源与视角在 URL 上长得一模一样（产品接入通则 A-2）。
     */
    Optional<ExportRecord> findExport(String bidId, String exportId);

    Optional<ExportRecord> findLatestExport(String bidId);

    record SourceFileRecord(
            String id, String bidId, String originalFileName, String objectKey,
            String mediaType, long fileSize, String contentHash, String parseStatus,
            String extractedText, String errorMessage,
            String overviewStatus, String overviewContent, String overviewErrorMessage,
            String scoringStatus, String scoringContent, String scoringErrorMessage
    ) {
        public SourceFileRecord(
                String id, String bidId, String originalFileName, String objectKey,
                String mediaType, long fileSize, String contentHash, String parseStatus,
                String extractedText, String errorMessage
        ) {
            this(id, bidId, originalFileName, objectKey, mediaType, fileSize, contentHash,
                    parseStatus, extractedText, errorMessage, "PENDING", null, null,
                    "PENDING", null, null);
        }
    }

    record SourceSegmentRecord(
            int sequence, String locatorType, String locator, String text
    ) {
    }

    /**
     * 个人素材。
     *
     * <p>{@code tenant} 与 {@code ownerId} 并存而不是二选一：归属人决定谁能编辑，
     * 工作空间决定这份素材属于哪个租户的数据。平台身份下两者不再一一对应——同一个人在
     * 两个工作空间里传的素材互不可见，所以读路径两个条件都带。
     */
    record AssetRecord(
            String id, String ownerId, TenantScope tenant, String category, String displayName,
            String originalFileName, String objectKey, String mediaType,
            long fileSize, String contentHash, String status
    ) {
    }

    record ExportRecord(
            String id, String bidId, int version, String fileName,
            String objectKey, long fileSize, String createdBy,
            String layoutJobId, String qaStatus
    ) {
    }

    record GenerationTaskExecution(
            String taskId,
            String bidId,
            String status,
            String snapshotId,
            String snapshotHash,
            String workflowRunId,
            int retryCount,
            boolean changed
    ) {
    }
}
