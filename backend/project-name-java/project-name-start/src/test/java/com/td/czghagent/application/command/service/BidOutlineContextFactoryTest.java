// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.BidDocument;
import com.td.czghagent.domain.model.BidProductionState;
import com.td.czghagent.domain.model.BidReferenceChunk;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.port.TenderAiGateway;
import com.td.czghagent.domain.repository.AuditRepository;
import com.td.czghagent.domain.repository.BidRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowableOfType;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 目录生成一个阶段的输入：从冻结的解读、选中的目录参考素材与标书本身拼出请求，
 * 并在输入已经变了的时候拒绝开始。
 *
 * <p>这里出错的样子都不报错：任务期间用户改了解读，目录照着旧解读生成并覆盖回去；
 * 评分原文与定位互换了位置，模型引用的出处全错；参考素材不设上限，一份大文件把请求撑爆；
 * 操作上下文从人推工作空间，多空间用户的审计记到别的空间上。
 */
class BidOutlineContextFactoryTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 15, 10, 0);
    private static final TenantScope TENANT = new TenantScope("org-1", "ws-7");
    private static final String TASK = "outline-task-1";

    private BidRepository repository;
    private BidAssetIngestionService ingestion;
    private BidOutlineContextFactory factory;

    private final BidDocument bid = new BidDocument("bid-1", "owner-1", TENANT, "B-1", "SCORING_CRITERIA",
            "智慧园区投标文件", 120, "OPEN", "OUTLINE", "GENERATING", false, null, NOW, NOW, 3);

    @BeforeEach
    void setUp() {
        repository = mock(BidRepository.class);
        ingestion = mock(BidAssetIngestionService.class);
        factory = new BidOutlineContextFactory(repository, ingestion, new BidCommandSupport(repository, mock(AuditRepository.class)));
        when(repository.findBidForTask("bid-1", "owner-1")).thenReturn(Optional.of(bid));
    }

    // ── 请求 ─────────────────────────────────────────────────────────────

    /**
     * 按排序号排列（而不是存储顺序）；评分原文与出处定位各归各位。
     *
     * <p>工作区与网关两边的记录里这两个字段的<strong>先后顺序相反</strong>，按位置照抄就会互换。
     *
     * <p>解读完整的判据是「恰好项目概述与技术评分各一条」，所以能走到这里的解读里不会有第三类——
     * 不在这里造一条其它类型去验过滤：那样的输入在前一步就被拒了，验到的是拒绝而不是过滤。
     */
    @Test
    void buildsTheRequestFromTheFrozenInterpretationInOrder() {
        stubWorkspace(workspace(List.of(
                criterion("c-score", "TECHNICAL_SCORING", "技术评分", "方案完整得20分", 2),
                criterion("c-overview", "PROJECT_OVERVIEW", "项目概述", "建设统一技术平台", 1)),
                task(TASK, 2), "FROZEN", List.of()));

        BidOutlineContextFactory.Context context = factory.load(TASK, "bid-1", "owner-1", "trace-9", "203.0.113.9");

        TenderAiGateway.OutlineRequest request = context.request();
        assertThat(request.requestId()).isEqualTo("trace-9");
        assertThat(request.title()).isEqualTo("智慧园区投标文件");
        assertThat(request.targetPages()).isEqualTo(120);
        assertThat(request.biddingMode()).isEqualTo("OPEN");
        assertThat(request.criteria()).extracting(TenderAiGateway.Criterion::id).containsExactly("c-overview", "c-score");
        TenderAiGateway.Criterion scoring = request.criteria().get(1);
        assertThat(scoring.description()).isEqualTo("方案完整得20分");
        assertThat(scoring.score()).isEqualTo(20.0);
        assertThat(scoring.sourceExcerpt()).isEqualTo("原文：方案完整得20分");
        assertThat(scoring.sourceLocator()).isEqualTo("第3章 评分办法");
        assertThat(request.references()).isEmpty();
    }

    /** 后台执行没有登录用户：租户取自标书本身，显示名留空而不是编一个。 */
    @Test
    void theOperationContextTakesTheTenantFromTheBidAndInventsNoName() {
        stubWorkspace(workspace(completeCriteria(), task(TASK, 2), "FROZEN", List.of()));

        BidOutlineContextFactory.Context context = factory.load(TASK, "bid-1", "owner-1", "trace-9", "203.0.113.9");

        assertThat(context.operation().user().id()).isEqualTo("owner-1");
        assertThat(context.operation().user().tenant()).isEqualTo(TENANT);
        assertThat(context.operation().user().roleCode()).isEqualTo("PLANNER");
        assertThat(context.operation().user().username()).isEmpty();
        assertThat(context.operation().user().displayName()).isEmpty();
        assertThat(context.operation().traceId()).isEqualTo("trace-9");
        assertThat(context.operation().ipAddress()).isEqualTo("203.0.113.9");
    }

    /** 只引用选中的、目录类的、归属人在该空间里看得见的素材；其余不解析。 */
    @Test
    void referencesOnlySelectedOutlineAssetsTheOwnerCanSee() {
        BidRepository.AssetRecord outlineAsset = asset("a-outline", "OUTLINE", "参考目录.docx");
        BidRepository.AssetRecord galleryAsset = asset("a-gallery", "GALLERY", "园区照片.png");
        when(repository.findAsset("a-outline", "owner-1", TENANT)).thenReturn(Optional.of(outlineAsset));
        when(repository.findAsset("a-gallery", "owner-1", TENANT)).thenReturn(Optional.of(galleryAsset));
        when(repository.findAsset("a-missing", "owner-1", TENANT)).thenReturn(Optional.empty());
        when(ingestion.ensureIngested(outlineAsset)).thenReturn(List.of(
                chunk("段落 1", "一、总体设计"), chunk("段落 2", "二、实施方案")));
        stubWorkspace(workspace(completeCriteria(), task(TASK, 2), "FROZEN",
                List.of("a-outline", "a-gallery", "a-missing")));

        TenderAiGateway.OutlineRequest request = factory.load(TASK, "bid-1", "owner-1", "trace-9", "ip").request();

        assertThat(request.references()).singleElement().satisfies(reference -> {
            assertThat(reference.id()).isEqualTo("a-outline");
            assertThat(reference.category()).isEqualTo("OUTLINE");
            assertThat(reference.name()).isEqualTo("参考目录.docx");
            assertThat(reference.summary()).isEqualTo("[段落 1] 一、总体设计\n[段落 2] 二、实施方案\n");
        });
        verify(ingestion, never()).ensureIngested(galleryAsset);
    }

    /** 一份大参考文件不能把请求撑爆：摘要封顶 5 万字。 */
    @Test
    void aReferenceSummaryIsCappedAt50000Characters() {
        BidRepository.AssetRecord outlineAsset = asset("a-outline", "OUTLINE", "超长目录.docx");
        when(repository.findAsset("a-outline", "owner-1", TENANT)).thenReturn(Optional.of(outlineAsset));
        List<BidReferenceChunk> chunks = new ArrayList<>();
        for (int index = 0; index < 3; index++) {
            chunks.add(chunk("段落 " + index, "章".repeat(30_000)));
        }
        when(ingestion.ensureIngested(outlineAsset)).thenReturn(chunks);
        stubWorkspace(workspace(completeCriteria(), task(TASK, 2), "FROZEN", List.of("a-outline")));

        TenderAiGateway.OutlineRequest request = factory.load(TASK, "bid-1", "owner-1", "trace-9", "ip").request();

        assertThat(request.references().getFirst().summary()).hasSize(50_000);
    }

    // ── 拒绝开始 ──────────────────────────────────────────────────────────

    @Test
    void aTaskThatIsNoLongerTheCurrentOneCannotStart() {
        stubWorkspace(workspace(completeCriteria(), task("another-task", 2), "FROZEN", List.of()));

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")))
                .extracting(BusinessException::getErrorCode, BusinessException::getHttpStatus)
                .containsExactly("BID_OUTLINE_INPUT_CHANGED", 409);
    }

    @Test
    void aBidWithoutAnOutlineTaskCannotStart() {
        stubWorkspace(workspace(completeCriteria(), null, "FROZEN", List.of()));

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")).getErrorCode())
                .isEqualTo("BID_OUTLINE_INPUT_CHANGED");
    }

    /** 任务建立之后标书又被改过（修订号前进了不止一步）：按旧输入生成的目录会覆盖掉新改动。 */
    @Test
    void aBidEditedAfterTheTaskWasCreatedCannotStart() {
        stubWorkspace(workspace(completeCriteria(), task(TASK, 1), "FROZEN", List.of()));

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")).getErrorCode())
                .isEqualTo("BID_OUTLINE_INPUT_CHANGED");
    }

    @Test
    void anUnfrozenInterpretationCannotDriveTheOutline() {
        stubWorkspace(workspace(completeCriteria(), task(TASK, 2), "DRAFT", List.of()));

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")))
                .extracting(BusinessException::getErrorCode, BusinessException::getHttpStatus)
                .containsExactly("BID_INTERPRETATION_NOT_FROZEN", 409);
    }

    @Test
    void anIncompleteInterpretationCannotDriveTheOutline() {
        stubWorkspace(workspace(List.of(criterion("c-overview", "PROJECT_OVERVIEW", "项目概述", "建设统一技术平台", 1)),
                task(TASK, 2), "FROZEN", List.of()));

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")))
                .extracting(BusinessException::getErrorCode, BusinessException::getHttpStatus)
                .containsExactly("BID_CRITERIA_REQUIRED", 400);
    }

    @Test
    void aBidThatNoLongerExistsIsNotFoundAndNothingIsLoaded() {
        when(repository.findBidForTask("bid-1", "owner-1")).thenReturn(Optional.empty());
        when(repository.existsBid("bid-1")).thenReturn(false);

        assertThat(errorOf(() -> factory.load(TASK, "bid-1", "owner-1", "t", "ip")))
                .extracting(BusinessException::getErrorCode, BusinessException::getHttpStatus)
                .containsExactly("BID_NOT_FOUND", 404);
        verify(repository, never()).loadWorkspace(any());
    }

    // ── 目录节点 ──────────────────────────────────────────────────────────

    /**
     * 模型给的是临时键：换成新标识并按键接上父子关系；只有一级节点带计划页数；
     * 排序号取模型给出的顺序；空白关键词与评分点剔除。
     */
    @Test
    void outlineNodesGetFreshIdsLinkedByKeyWithPagesOnlyOnTopLevel() {
        TenderAiGateway.OutlinePlan plan = new TenderAiGateway.OutlinePlan(List.of(
                new TenderAiGateway.OutlineNode("k1", null, 1, " 总体设计 ", 30, " 讲清架构 ", List.of("架构", " "), null),
                new TenderAiGateway.OutlineNode("k2", "k1", 2, "网络架构", 12, "", null, List.of("SP-001", ""))),
                List.of(), null, List.of());

        List<BidWorkspace.OutlineNode> nodes = factory.toNodes(plan);

        BidWorkspace.OutlineNode root = nodes.get(0);
        BidWorkspace.OutlineNode child = nodes.get(1);
        assertThat(root.id()).isNotBlank().isNotEqualTo("k1");
        assertThat(root.parentId()).isNull();
        assertThat(child.parentId()).isEqualTo(root.id());
        assertThat(root.title()).isEqualTo("总体设计");
        assertThat(root.taskBrief()).isEqualTo("讲清架构");
        assertThat(root.plannedPages()).isEqualTo(30);
        assertThat(child.plannedPages()).isZero();
        assertThat(nodes).extracting(BidWorkspace.OutlineNode::sortOrder).containsExactly(0, 1);
        assertThat(root.mustKeywords()).containsExactly("架构");
        assertThat(root.scoringPointIds()).isEmpty();
        assertThat(child.mustKeywords()).isEmpty();
        assertThat(child.scoringPointIds()).containsExactly("SP-001");
    }

    @Test
    void aBlankOrOverlongTitleFromTheModelIsRejected() {
        for (String title : List.of("   ", "目".repeat(201))) {
            TenderAiGateway.OutlinePlan plan = new TenderAiGateway.OutlinePlan(List.of(
                    new TenderAiGateway.OutlineNode("k1", null, 1, title, 30, "", List.of(), List.of())),
                    List.of(), null, List.of());

            assertThat(errorOf(() -> factory.toNodes(plan)))
                    .extracting(BusinessException::getErrorCode, BusinessException::getHttpStatus)
                    .containsExactly("BID_AI_OUTLINE_INVALID", 502);
        }
    }

    // ── 构造 ─────────────────────────────────────────────────────────────

    private void stubWorkspace(BidWorkspace workspace) {
        when(repository.loadWorkspace(bid)).thenReturn(workspace);
    }

    private BidWorkspace workspace(List<BidWorkspace.Criterion> criteria, BidWorkspace.OutlineTask task,
                                   String interpretationStatus, List<String> selectedAssetIds) {
        BidProductionState production = new BidProductionState(interpretationStatus, 1, "i-hash", "DRAFT", 0, null,
                "DRAFT", 0, null, null, List.of(), List.of(), List.of(), List.of(), null);
        return new BidWorkspace(bid, null, criteria, List.of(), List.of(), task, null, selectedAssetIds, List.of(), production);
    }

    private static List<BidWorkspace.Criterion> completeCriteria() {
        return List.of(
                criterion("c-overview", "PROJECT_OVERVIEW", "项目概述", "建设统一技术平台", 1),
                criterion("c-score", "TECHNICAL_SCORING", "技术评分", "方案完整得20分", 2));
    }

    private static BidWorkspace.Criterion criterion(String id, String type, String title, String description, int sortOrder) {
        return new BidWorkspace.Criterion(id, type, title, description, 20.0, "原文：" + description,
                "第3章 评分办法", "TECHNICAL", "HIGH", sortOrder, false);
    }

    private static BidWorkspace.OutlineTask task(String id, long inputRevision) {
        return new BidWorkspace.OutlineTask(id, "RUNNING", "SKELETON", 10, inputRevision, "run-1", null, NOW, NOW, null,
                List.of());
    }

    private static BidRepository.AssetRecord asset(String id, String category, String fileName) {
        return new BidRepository.AssetRecord(id, "owner-1", TENANT, category, fileName, fileName,
                "assets/" + id, "application/octet-stream", 10, "hash", "ACTIVE");
    }

    private static BidReferenceChunk chunk(String locator, String content) {
        return new BidReferenceChunk("chunk-" + locator, "a-outline", "OUTLINE", "参考目录", 0, "", locator, content,
                "hash", content.length());
    }

    private static BusinessException errorOf(Runnable action) {
        return catchThrowableOfType(BusinessException.class, action::run);
    }
}
