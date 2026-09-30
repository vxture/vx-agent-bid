package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.model.BidDocument;
import com.td.czghagent.domain.model.BidExport;
import com.td.czghagent.domain.model.BidReferenceAsset;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidSummary;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.model.BidWorkspaceViews;
import com.td.czghagent.domain.model.PageCursor;
import com.td.czghagent.domain.repository.BidProductionRepository;
import com.td.czghagent.domain.repository.BidRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;

/** Domain-port adapter; focused collaborators own the SQL for each persistence concern. */
@Repository
public class JdbcBidRepository implements BidRepository {
    private final JdbcBidWorkspaceReader reader;
    private final JdbcBidDraftPersistence drafts;
    private final JdbcBidAssetPersistence assets;
    private final JdbcBidTaskExportPersistence tasks;
    private final BidProductionRepository productionRepository;

    public JdbcBidRepository(JdbcTemplate jdbcTemplate,
                             BidProductionRepository productionRepository) {
        this.productionRepository = productionRepository;
        this.tasks = new JdbcBidTaskExportPersistence(jdbcTemplate);
        this.reader = new JdbcBidWorkspaceReader(jdbcTemplate, productionRepository, tasks);
        this.drafts = new JdbcBidDraftPersistence(jdbcTemplate);
        this.assets = new JdbcBidAssetPersistence(jdbcTemplate);
    }

    @Override
    public void insertBid(BidDocument bid) {
        drafts.insertBid(bid);
    }

    @Override
    public List<BidSummary> listBids(String ownerId, TenantScope tenant, PageCursor after, int limit) {
        return reader.listBids(ownerId, tenant, after, limit);
    }

    @Override
    public Optional<BidDocument> findBid(String bidId, String ownerId, TenantScope tenant) {
        return reader.findBid(bidId, ownerId, tenant);
    }

    @Override
    public Optional<BidDocument> findBidForTask(String bidId, String ownerId) {
        return reader.findBidForTask(bidId, ownerId);
    }

    @Override
    public boolean existsBid(String bidId) {
        return reader.existsBid(bidId);
    }

    /**
     * 工作台读取在<strong>同一个快照</strong>里完成。
     *
     * <p>读取器分多条语句取目录、章节、任务、导出与生产状态。不包事务时每条语句各看
     * 各的已提交数据：重新生成目录恰好在两条语句之间提交，一次响应里就会出现
     * 「目录任务已完成」配「旧章节、旧页数」——写入侧是原子的，撕裂发生在读这一侧。
     *
     * <p>{@code REPEATABLE_READ} 不能省：PostgreSQL 默认的读已提交级别下，事务内每条语句
     * 仍各取一个快照，单加事务注解等于没加。已处于读写事务中的调用方会加入外层事务、
     * 沿用外层隔离级别——那些路径本就在自己的写事务里读，不在本修复范围内。
     */
    @Override
    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public BidWorkspace loadWorkspace(BidDocument bid) {
        return reader.loadWorkspace(bid);
    }

    /** 与 {@link #loadWorkspace} 同理：任务、导出与生产状态分几条语句读，要在同一个快照里。 */
    @Override
    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public BidWorkspaceViews.Metadata loadMetadata(BidDocument bid) {
        return reader.loadMetadata(bid);
    }

    @Override
    public BidWorkspaceViews.OutlineView loadOutline(String bidId) {
        return reader.loadOutline(bidId);
    }

    @Override
    public Optional<BidWorkspaceViews.ChapterDetail> findChapterDetail(
            String bidId, String chapterId) {
        return reader.findChapterDetail(bidId, chapterId);
    }

    @Override
    public BidWorkspaceViews.GenerationProgress loadGenerationProgress(String bidId) {
        return reader.loadGenerationProgress(bidId);
    }

    @Override
    public boolean updateSetup(String bidId, String title, int targetPages,
                               String biddingMode, long revision) {
        return drafts.updateSetup(bidId, title, targetPages, biddingMode, revision);
    }

    @Override
    @Transactional
    public void insertSourceFile(SourceFileRecord source) {
        drafts.insertSourceFile(source);
    }

    @Override
    public Optional<SourceFileRecord> findSourceFile(String bidId) {
        return drafts.findSourceFile(bidId);
    }

    @Override
    @Transactional
    public boolean beginSourceParse(String sourceId, String bidId) {
        return drafts.beginSourceParse(sourceId, bidId);
    }

    @Override
    public boolean updateSourceParseProgress(String sourceId, String stage, int progress) {
        return drafts.updateSourceParseProgress(sourceId, stage, progress);
    }

    @Override
    @Transactional
    public boolean saveParsedSource(String sourceId, String bidId, String extractedText,
                                    List<SourceSegmentRecord> segments) {
        return drafts.saveParsedSource(sourceId, bidId, extractedText, segments);
    }

    @Override
    public List<SourceSegmentRecord> listSourceSegments(String sourceId) {
        return drafts.listSourceSegments(sourceId);
    }

    @Override
    public boolean beginInterpretationObject(String sourceId, String objectType) {
        return drafts.beginInterpretationObject(sourceId, objectType);
    }

    @Override
    @Transactional
    public boolean completeInterpretationObject(
            String sourceId, String bidId, String objectType, String content,
            BidWorkspace.Criterion criterion
    ) {
        return drafts.completeInterpretationObject(
                sourceId, bidId, objectType, content, criterion);
    }

    @Override
    public boolean failInterpretationObject(
            String sourceId, String objectType, String errorMessage
    ) {
        return drafts.failInterpretationObject(sourceId, objectType, errorMessage);
    }

    @Override
    @Transactional
    public boolean completeSourceParse(String sourceId, String bidId) {
        return drafts.completeSourceParse(sourceId, bidId);
    }

    @Override
    @Transactional
    public boolean failSourceParse(String sourceId, String bidId, String errorMessage) {
        return drafts.failSourceParse(sourceId, bidId, errorMessage);
    }

    @Override
    @Transactional
    public void replaceCriteria(String bidId, List<BidWorkspace.Criterion> criteria,
                                boolean manual) {
        drafts.replaceCriteria(bidId, criteria, manual);
    }

    @Override
    @Transactional
    public void replaceAssetSelections(String bidId, String ownerId, TenantScope tenant,
                                       List<String> assetIds) {
        drafts.replaceAssetSelections(bidId, ownerId, tenant, assetIds);
    }

    @Override
    @Transactional
    public void replaceOutline(String bidId, List<BidWorkspace.OutlineNode> nodes,
                               boolean confirmed) {
        drafts.replaceOutline(bidId, nodes, confirmed);
    }

    @Override
    public void confirmOutline(String bidId) {
        drafts.confirmOutline(bidId);
    }

    @Override
    @Transactional
    public String createOutlineTask(String bidId) {
        return tasks.createOutlineTask(bidId);
    }

    @Override
    public void assignOutlineWorkflowRun(String taskId, String workflowRunId) {
        tasks.assignOutlineWorkflowRun(taskId, workflowRunId);
    }

    @Override
    public boolean updateOutlineTaskProgress(String taskId, String stage, int progress) {
        return tasks.updateOutlineTaskProgress(taskId, stage, progress);
    }

    @Override
    @Transactional
    public boolean completeOutlineTask(String taskId, String bidId,
                                       List<BidWorkspace.OutlineNode> nodes, List<String> warnings) {
        drafts.replaceGeneratedOutline(bidId, nodes);
        productionRepository.markOutlineReview(bidId, "The generated outline is ready for review");
        if (!tasks.completeOutlineTask(taskId, warnings)) {
            throw new IllegalStateException("The outline task stopped before its result was committed");
        }
        return true;
    }

    @Override
    @Transactional
    public boolean failOutlineTask(String taskId, String bidId, String errorMessage) {
        return tasks.failOutlineTask(taskId, bidId, errorMessage);
    }

    @Override
    @Transactional
    public String createGenerationTask(String bidId, int totalUnits) {
        return tasks.createGenerationTask(bidId, totalUnits);
    }

    @Override
    public void startGenerationTask(String taskId) {
        tasks.startGenerationTask(taskId);
    }

    @Override
    public boolean saveGeneratedChapter(String chapterId, String content) {
        return tasks.saveGeneratedChapter(chapterId, content);
    }

    @Override
    public void advanceGenerationTask(String taskId) {
        tasks.advanceGenerationTask(taskId);
    }

    @Override
    @Transactional
    public boolean completeGenerationTask(String taskId, String bidId) {
        return tasks.completeGenerationTask(taskId, bidId);
    }

    @Override
    @Transactional
    public boolean failGenerationTask(String taskId, String bidId, String message) {
        return tasks.failGenerationTask(taskId, bidId, message);
    }

    @Override
    @Transactional
    public GenerationTaskExecution pauseGenerationTask(String bidId) {
        return tasks.pauseGenerationTask(bidId);
    }

    @Override
    @Transactional
    public GenerationTaskExecution resumeGenerationTask(String bidId) {
        return tasks.resumeGenerationTask(bidId);
    }

    @Override
    @Transactional
    public boolean updateChapter(String bidId, String chapterId, String content, long revision) {
        return drafts.updateChapter(bidId, chapterId, content, revision);
    }

    @Override
    public void markContentStale(String bidId) {
        drafts.markContentStale(bidId);
    }

    @Override
    public void insertAsset(AssetRecord asset) {
        assets.insertAsset(asset);
    }

    @Override
    public List<BidReferenceAsset> listAssets(
            String ownerId, TenantScope tenant, String category, String keyword,
            PageCursor after, int limit) {
        return assets.listAssets(ownerId, tenant, category, keyword, after, limit);
    }

    @Override
    public Optional<BidReferenceAsset> findActiveAsset(String assetId, String ownerId, TenantScope tenant) {
        return assets.findActiveAsset(assetId, ownerId, tenant);
    }

    @Override
    public Optional<AssetRecord> findAsset(String assetId, String ownerId, TenantScope tenant) {
        return assets.findAsset(assetId, ownerId, tenant);
    }

    @Override
    @Transactional
    public void replaceAssetChunks(String assetId, List<BidReferenceChunk> chunks) {
        assets.replaceAssetChunks(assetId, chunks);
    }

    @Override
    public List<BidReferenceChunk> listAssetChunks(List<String> assetIds) {
        return assets.listAssetChunks(assetIds);
    }

    @Override
    public void markAssetIngestion(String assetId, String status, String errorMessage) {
        assets.markAssetIngestion(assetId, status, errorMessage);
    }

    @Override
    public boolean removeAsset(String assetId, String ownerId, TenantScope tenant) {
        return assets.removeAsset(assetId, ownerId, tenant);
    }

    @Override
    public int nextExportVersion(String bidId) {
        return tasks.nextExportVersion(bidId);
    }

    @Override
    @Transactional
    public void insertExport(ExportRecord export) {
        tasks.insertExport(export);
    }

    @Override
    @Transactional
    public OptionalLong raiseMeteredCharacters(String bidId, long characters) {
        return tasks.raiseMeteredCharacters(bidId, characters);
    }

    @Override
    public List<BidExport> listExports(String bidId, PageCursor after, int limit) {
        return tasks.listExports(bidId, after, limit);
    }

    @Override
    public Optional<BidExport> findExportSummary(String bidId, String exportId) {
        return tasks.findExportSummary(bidId, exportId);
    }

    @Override
    public Optional<ExportRecord> findExport(String bidId, String exportId) {
        return tasks.findExport(bidId, exportId);
    }

    @Override
    public Optional<ExportRecord> findLatestExport(String bidId) {
        return tasks.findLatestExport(bidId);
    }
}
