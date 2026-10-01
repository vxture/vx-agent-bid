// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.exception.AiGatewayException;
import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.BidGenerationPlan;
import com.td.czghagent.domain.model.BidGenerationSnapshot;
import com.td.czghagent.domain.model.BidGenerationUnit;
import com.td.czghagent.domain.model.BidProductionRules;
import com.td.czghagent.domain.port.TenderAiGateway;
import com.td.czghagent.domain.repository.BidProductionRepository;
import com.td.czghagent.domain.repository.BidRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowableOfType;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * 正文分段生成：一个写作单元从领取到提交的整条路径。
 *
 * <p>这里出错的样子都不报错：重试时把已经成功的单元再写一遍（重复计费，覆盖用户已看过的正文）；
 * 人工改过的章节被模型覆盖；两个活动同时写一个单元；带着内部标识的草稿直接入库；
 * 失败时不记诊断，事后查不出是模型截断还是网络；未写完的任务被定稿。
 *
 * <p>即时质检 {@link BidContentQualityGuard} 按真实规则运行，不打桩：草稿里出现 UUID 就是阻断问题，
 * 通顺的正文就是干净的——测试验的是服务怎么对待这两种结果，而不是替身怎么回答。
 */
class BidGenerationServiceTest {

    private static final String TASK = "task-1";
    private static final String BID = "bid-1";
    private static final String OWNER = "owner-1";
    private static final String SNAPSHOT_HASH = "abcdef0123456789abcdef";
    private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 15, 10, 0);
    private static final String CLEAN_HTML = "<p>投标人将按照招标文件要求完成系统部署与联调测试。</p>";
    private static final String LEAKING_HTML = "<p>登记编号 123e4567-e89b-42d3-a456-426614174000 已归档。</p>";

    private BidRepository bidRepository;
    private BidProductionRepository productionRepository;
    private TenderAiGateway gateway;
    private BidGenerationPlanningService planningService;
    private BidGenerationExecutionPlanner executionPlanner;
    private BidUnitDraftFactory draftFactory;
    private BidBranchBlueprintService blueprintService;
    private BidAiExecutionService aiExecutionService;
    private BidContentReviewService reviewService;
    private BidContentFinalizationService finalizationService;
    private BidGenerationService service;

    private final BidGenerationSnapshot snapshot = new BidGenerationSnapshot("snap-1", TASK, BID, OWNER, SNAPSHOT_HASH,
            "智慧园区投标文件", "OPEN", 120, 1, 1, "", "", "", "", "prompt-v3", NOW,
            List.of(), List.of(), List.of(), List.of());
    private final TenderAiGateway.BranchBlueprint blueprint = new TenderAiGateway.BranchBlueprint(
            "统一平台", List.of(), List.of(), List.of(), List.of(), List.of());
    private final TenderAiGateway.ChapterDraftRequest draftRequest = new TenderAiGateway.ChapterDraftRequest(
            "req-1", "智慧园区投标文件", "OPEN", null, blueprint, List.of(), TenderAiGateway.FrozenDictionary.empty(),
            List.of(), "", "", "上一段摘要", "", "", "", List.of(), "下一段提要", 800, 1, 1, "总体设计", "", "", "");

    @BeforeEach
    void setUp() {
        bidRepository = mock(BidRepository.class);
        productionRepository = mock(BidProductionRepository.class);
        gateway = mock(TenderAiGateway.class);
        planningService = mock(BidGenerationPlanningService.class);
        executionPlanner = mock(BidGenerationExecutionPlanner.class);
        draftFactory = mock(BidUnitDraftFactory.class);
        blueprintService = mock(BidBranchBlueprintService.class);
        aiExecutionService = mock(BidAiExecutionService.class);
        reviewService = mock(BidContentReviewService.class);
        finalizationService = mock(BidContentFinalizationService.class);
        // 构造时读一次：必须先打桩，否则整次测试里提供方与模型名都是 null。
        when(aiExecutionService.providerName()).thenReturn("deepseek");
        when(aiExecutionService.fastModelName()).thenReturn("deepseek-chat");
        service = new BidGenerationService(bidRepository, productionRepository, gateway, planningService,
                executionPlanner, draftFactory, blueprintService, aiExecutionService, reviewService, finalizationService);
        when(productionRepository.loadGenerationSnapshot("snap-1", OWNER)).thenReturn(snapshot);
    }

    // ── 建任务与准备 ─────────────────────────────────────────────────────

    @Test
    void createTaskHandsBackThePlannedLaunch() {
        when(planningService.create(any())).thenReturn(new BidGenerationPlanningService.Launch(TASK, "snap-1", SNAPSHOT_HASH));

        BidGenerationService.GenerationLaunch launch = service.createTask(null);

        assertThat(launch).isEqualTo(new BidGenerationService.GenerationLaunch(TASK, "snap-1", SNAPSHOT_HASH));
    }

    @Test
    void prepareStartsTheTaskRecordsTheSnapshotAndListsTheUnits() {
        when(productionRepository.listGenerationUnits(TASK)).thenReturn(List.of(unit("u1", "PENDING"), unit("u2", "PENDING")));

        assertThat(service.prepare(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH)).containsExactly("u1", "u2");

        verify(bidRepository).startGenerationTask(TASK);
        verify(productionRepository).appendEvent(TASK, BID, null, "TASK_STARTED", "正文分段生成已开始，输入快照 abcdef012345");
    }

    @Test
    void preparePlanHandsTheSnapshotAndUnitsToTheExecutionPlanner() {
        List<BidGenerationUnit> units = List.of(unit("u1", "PENDING"));
        BidGenerationPlan plan = new BidGenerationPlan(List.of(new BidGenerationPlan.Lane("n1", "总体设计", 800, List.of("u1"))), 2);
        when(productionRepository.listGenerationUnits(TASK)).thenReturn(units);
        when(executionPlanner.plan(snapshot, units)).thenReturn(plan);

        assertThat(service.preparePlan(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH)).isSameAs(plan);
    }

    /** 快照是不可变输入：任务号、标书、哈希任何一个对不上都拒绝，不开始任务。 */
    @Test
    void aSnapshotThatDoesNotMatchTheTaskIsRefused() {
        for (String[] mismatch : new String[][]{
                {"other-task", BID, SNAPSHOT_HASH}, {TASK, "other-bid", SNAPSHOT_HASH}, {TASK, BID, "other-hash-0000"}}) {
            IllegalStateException failure = catchThrowableOfType(IllegalStateException.class,
                    () -> service.prepare(mismatch[0], mismatch[1], OWNER, "snap-1", mismatch[2]));

            assertThat(failure).hasMessage("生成任务与不可变快照不匹配");
        }
        verify(bidRepository, never()).startGenerationTask(anyString());
    }

    // ── 领取单元 ─────────────────────────────────────────────────────────

    /** Temporal 重试时单元可能已经写完：直接跳过，不再调模型——否则重复计费，还会覆盖已经给人看过的正文。 */
    @Test
    void aSucceededOrSkippedUnitIsNotWrittenAgain() {
        for (String status : List.of("SUCCEEDED", "SKIPPED")) {
            when(productionRepository.findGenerationUnit("u1")).thenReturn(Optional.of(unit("u1", status)));

            service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");
        }

        verify(productionRepository, never()).startGenerationUnit(anyString());
        verifyNoInteractions(gateway, draftFactory, blueprintService);
    }

    /** 人工改过的章节保留人工版本：跳过这个单元，模型不碰它。 */
    @Test
    void aManuallyEditedChapterKeepsTheManualVersion() {
        when(productionRepository.findGenerationUnit("u1")).thenReturn(Optional.of(unit("u1", "PENDING")));
        when(draftFactory.outlineForChapter(snapshot, "c1")).thenReturn(outline("MANUAL"));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        verify(productionRepository).skipGenerationUnit("u1", TASK, BID, "c1", "人工版本已保留");
        verify(productionRepository, never()).startGenerationUnit(anyString());
        verifyNoInteractions(gateway);
    }

    /** 两个活动抢同一个单元：没抢到的一方若发现对方已经写完就安静退出，否则失败让 Temporal 稍后重试。 */
    @Test
    void aUnitClaimedByAnotherActivityIsLeftToIt() {
        when(draftFactory.outlineForChapter(snapshot, "c1")).thenReturn(outline("PENDING"));
        when(productionRepository.startGenerationUnit("u1")).thenReturn(false);
        when(productionRepository.findGenerationUnit("u1"))
                .thenReturn(Optional.of(unit("u1", "PENDING")), Optional.of(unit("u1", "RUNNING")));

        IllegalStateException failure = catchThrowableOfType(IllegalStateException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1"));

        assertThat(failure).hasMessage("生成单元正在被其他活动处理");
        verifyNoInteractions(gateway);
    }

    @Test
    void aUnitTheOtherActivityAlreadyFinishedEndsQuietly() {
        when(draftFactory.outlineForChapter(snapshot, "c1")).thenReturn(outline("PENDING"));
        when(productionRepository.startGenerationUnit("u1")).thenReturn(false);
        when(productionRepository.findGenerationUnit("u1"))
                .thenReturn(Optional.of(unit("u1", "PENDING")), Optional.of(unit("u1", "SUCCEEDED")));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        verifyNoInteractions(gateway);
    }

    @Test
    void aUnitThatIsMissingOrBelongsToAnotherTaskIsRefused() {
        when(productionRepository.findGenerationUnit("missing")).thenReturn(Optional.empty());
        when(productionRepository.findGenerationUnit("foreign")).thenReturn(Optional.of(new BidGenerationUnit(
                "foreign", "other-task", BID, "c1", 1, "总体设计", "idem-foreign", "PENDING", 0, 800,
                null, null, null, null, null, NOW)));

        assertThat(catchThrowableOfType(IllegalStateException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "missing"))).hasMessage("生成单元不存在");
        assertThat(catchThrowableOfType(IllegalStateException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "foreign"))).hasMessage("生成单元不属于当前任务");
    }

    // ── 写作与提交 ────────────────────────────────────────────────────────

    /**
     * 干净的草稿：先取分支蓝图再写；按快照哈希与幂等键登记一次模型调用；提交时带上字数、预算状态、
     * 组装后的章节、模型诊断与提供方——事后按这些查得出每一段是谁、用多少 token 写的。
     */
    @Test
    void aCleanDraftIsCommittedWithItsRunBudgetAndDiagnostics() {
        BidGenerationUnit unit = claimable("u1", 800);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(CLEAN_HTML));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        verify(draftFactory).create(snapshot, unit, List.of(unit), blueprint);
        ArgumentCaptor<BidProductionRepository.AiRunStart> run = ArgumentCaptor.forClass(BidProductionRepository.AiRunStart.class);
        verify(productionRepository).beginAiRun(run.capture());
        assertThat(run.getValue().operationType()).isEqualTo("CHAPTER_DRAFT");
        assertThat(run.getValue().generationUnitId()).isEqualTo("u1");
        assertThat(run.getValue().snapshotId()).isEqualTo("snap-1");
        assertThat(run.getValue().provider()).isEqualTo("deepseek");
        assertThat(run.getValue().modelName()).isEqualTo("deepseek-chat");
        assertThat(run.getValue().promptVersion()).isEqualTo("prompt-v3");
        assertThat(run.getValue().idempotencyKey()).isEqualTo("idem-u1:draft");
        assertThat(run.getValue().inputSnapshotHash()).isEqualTo(BidProductionRules.generationSnapshotHash(SNAPSHOT_HASH, "idem-u1"));

        GeneratedCommit commit = committed();
        int visible = BidContentQualityGuard.visibleCharacterCount(CLEAN_HTML);
        assertThat(commit.value().unitContent()).isEqualTo(CLEAN_HTML);
        assertThat(commit.value().visibleCharacters()).isEqualTo(visible);
        assertThat(commit.value().budgetVarianceRatio()).isEqualTo((visible - 800) / 800.0);
        assertThat(commit.value().budgetStatus()).isEqualTo("WITHIN_BUDGET");
        assertThat(commit.value().aiRunId()).isEqualTo("run-1");
        assertThat(commit.value().aiRunAttemptId()).isEqualTo("attempt-1");
        assertThat(commit.value().unitSummary()).isEqualTo("本段摘要");
        assertThat(commit.value().assembledChapterContent()).isEqualTo("<p>组装后的总体设计</p>");
        assertThat(commit.value().chapterSummary()).isEqualTo("章节摘要");
        assertThat(commit.value().provider()).isEqualTo("deepseek");
        assertThat(commit.value().modelName()).isEqualTo("deepseek-chat");
        assertThat(commit.value().inputTokens()).isEqualTo(1000L);
        assertThat(commit.value().outputTokens()).isEqualTo(400L);
        assertThat(commit.value().finishReason()).isEqualTo("stop");
        assertThat(commit.value().responseHash()).isEqualTo("resp-hash");
        verify(aiExecutionService, never()).revise(anyString(), anyString(), anyString(), anyString(), any());
    }

    /**
     * 记下的是<strong>实际应答的</strong>模型：Atlas 按路由挂载、故障转移后还可能换成兜底模型，
     * 配置名只是开始时的猜测。v0.1.27 只改了单次调用的完成路径，正文分段走的是这条提交，
     * 生产上所有正文运行仍记着配置名（2026-10-02）。
     */
    @Test
    void theCommitCarriesTheModelAtlasReportsNotTheConfiguredOne() {
        claimable("u1", 800);
        TenderAiGateway.AiResponse<TenderAiGateway.ChapterDraft> echoed = response(CLEAN_HTML);
        when(gateway.draftChapter(draftRequest)).thenReturn(new TenderAiGateway.AiResponse<>(echoed.data(),
                new TenderAiGateway.AiDiagnostics("stop", 120, "resp-hash", 1000L, 400L, 50L, 10L, 1,
                        "doubao-seed-2-0-lite-260428")));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        assertThat(committed().value().modelName()).isEqualTo("doubao-seed-2-0-lite-260428");
    }

    /**
     * 超出预算 15% 以上标为超预算，比例按预算算——排版前据此判断哪几段写长了。
     *
     * <p>预算取在边界两侧，而不是远远低于字数：第一版用 10 字预算对 24 字草稿，门槛放宽到 50%
     * 照样判超预算，反证实测验不出门槛（S6 绿）。这里的超预算一例只超过 15% 一点、远不到 50%。
     */
    @Test
    void aDraftJustOverFifteenPercentOfBudgetIsMarkedOverBudget() {
        int visible = BidContentQualityGuard.visibleCharacterCount(CLEAN_HTML);
        int budget = (int) Math.floor(visible / 1.15);
        // 判据先验会不会动：预算必须落在「超过 15%、不到 50%」之间。
        assertThat(visible).isGreaterThan((int) (budget * 1.15)).isLessThan((int) (budget * 1.5));
        claimable("u1", budget);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(CLEAN_HTML));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        GeneratedCommit commit = committed();
        assertThat(commit.value().budgetStatus()).isEqualTo("OVER_BUDGET");
        assertThat(commit.value().budgetVarianceRatio()).isEqualTo((visible - budget) / (double) budget);
    }

    @Test
    void aDraftWithinFifteenPercentOfBudgetIsWithinBudget() {
        int visible = BidContentQualityGuard.visibleCharacterCount(CLEAN_HTML);
        int budget = (int) Math.ceil(visible / 1.15);
        assertThat((double) visible).isGreaterThan(budget).isLessThanOrEqualTo(budget * 1.15);
        claimable("u1", budget);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(CLEAN_HTML));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        assertThat(committed().value().budgetStatus()).isEqualTo("WITHIN_BUDGET");
    }

    /** 草稿带出内部标识：按问题交给模型重写一次，重写干净就提交重写后的正文，并记一条修订事件。 */
    @Test
    void aDraftLeakingAnInternalIdentifierIsRevisedAndTheRevisionIsCommitted() {
        claimable("u1", 800);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(LEAKING_HTML));
        when(aiExecutionService.revise(eq(BID), eq(TASK), eq("snap-1"), eq("chapter-unit-quality-repair-v1"), any()))
                .thenReturn(candidate(CLEAN_HTML));

        service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1");

        ArgumentCaptor<TenderAiGateway.RevisionRequest> revision = ArgumentCaptor.forClass(TenderAiGateway.RevisionRequest.class);
        verify(aiExecutionService).revise(eq(BID), eq(TASK), eq("snap-1"), eq("chapter-unit-quality-repair-v1"), revision.capture());
        assertThat(revision.getValue().requestId()).isEqualTo("idem-u1-quality-1");
        assertThat(revision.getValue().mode()).isEqualTo("REWRITE");
        assertThat(revision.getValue().selectedHtml()).isEqualTo(LEAKING_HTML);
        // 上文取前一段正文，没有时退回前一段摘要。
        assertThat(revision.getValue().beforeContext()).isEqualTo("上一段摘要");
        assertThat(revision.getValue().afterContext()).isEqualTo("下一段提要");
        // 修订指令说出问题本身（带出被泄露的标识），模型才知道删什么。
        assertThat(revision.getValue().instruction()).contains("123e4567-e89b-42d3-a456-426614174000");
        verify(productionRepository).appendEvent(eq(TASK), eq(BID), eq("c1"), eq("UNIT_QUALITY_REVISED"), anyString());
        assertThat(committed().value().unitContent()).isEqualTo(CLEAN_HTML);
    }

    /**
     * 修两轮仍不过：单元失败并记下原因与这次草稿的诊断，不提交；异常原样抛出交给 Temporal。
     * 绝不带着内部标识入库。
     */
    @Test
    void aDraftStillBlockedAfterTwoRepairsFailsTheUnitWithItsDiagnostics() {
        claimable("u1", 800);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(LEAKING_HTML));
        when(aiExecutionService.revise(anyString(), anyString(), anyString(), anyString(), any())).thenReturn(candidate(LEAKING_HTML));

        BusinessException failure = catchThrowableOfType(BusinessException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1"));

        assertThat(failure.getErrorCode()).isEqualTo("BID_CHAPTER_QUALITY_BLOCKED");
        assertThat(failure.getMessage()).startsWith("章节即时质检未通过：").contains("INTERNAL_IDENTIFIER_LEAK");
        verify(aiExecutionService, times(2)).revise(anyString(), anyString(), anyString(), anyString(), any());
        verify(productionRepository, never()).completeGeneratedUnit(any());
        verify(productionRepository).failGenerationUnit(eq("u1"), eq(TASK), eq(BID), eq("c1"), eq("run-1"), eq("attempt-1"),
                eq("BID_CHAPTER_QUALITY_BLOCKED"), eq(failure.getMessage()), anyLong(), isNull(),
                eq(1000L), eq(400L), eq(50L), eq(10L), eq("stop"), eq(120), eq("resp-hash"), eq(1));
    }

    @Test
    void aRevisionWithNoContentIsABlockedUnitNotAnEmptyChapter() {
        claimable("u1", 800);
        when(gateway.draftChapter(draftRequest)).thenReturn(response(LEAKING_HTML));
        when(aiExecutionService.revise(anyString(), anyString(), anyString(), anyString(), any())).thenReturn(candidate("   "));

        BusinessException failure = catchThrowableOfType(BusinessException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1"));

        assertThat(failure.getErrorCode()).isEqualTo("BID_CHAPTER_QUALITY_BLOCKED");
        assertThat(failure.getMessage()).isEqualTo("章节即时修订未返回有效内容");
        verify(productionRepository, never()).completeGeneratedUnit(any());
    }

    /** 模型出口失败：记网关给的码、失败原因与它带回的诊断——事后分得清是截断、超时还是拒票。 */
    @Test
    void aGatewayFailureRecordsTheGatewayCodeReasonAndDiagnostics() {
        claimable("u1", 800);
        AiGatewayException gatewayFailure = new AiGatewayException("AI_MODEL_TIMEOUT", "模型超时", 504, "TIMEOUT",
                "length", 64, "partial-hash", 3, 900L, 20L, 5L, 2L, "chapter", 30_000L);
        when(gateway.draftChapter(draftRequest)).thenThrow(gatewayFailure);

        AiGatewayException thrown = catchThrowableOfType(AiGatewayException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1"));

        assertThat(thrown).isSameAs(gatewayFailure);
        verify(productionRepository).failGenerationUnit(eq("u1"), eq(TASK), eq(BID), eq("c1"), eq("run-1"), eq("attempt-1"),
                eq("AI_MODEL_TIMEOUT"), eq("模型超时"), anyLong(), eq("TIMEOUT"),
                eq(900L), eq(20L), eq(5L), eq(2L), eq("length"), eq(64), eq("partial-hash"), eq(3));
    }

    /** 还没登记模型调用就失败（蓝图取不到）：不编一个调用号，诊断为空，码按通用模型错误。 */
    @Test
    void aFailureBeforeTheModelRunIsRecordedWithoutARun() {
        claimable("u1", 800);
        when(blueprintService.resolve(snapshot, unit("u1", "RUNNING", 800))).thenThrow(new IllegalStateException("蓝图生成失败"));

        catchThrowableOfType(IllegalStateException.class,
                () -> service.generateUnit(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH, "u1"));

        verify(productionRepository, never()).beginAiRun(any());
        verify(productionRepository).failGenerationUnit(eq("u1"), eq(TASK), eq(BID), eq("c1"), isNull(), isNull(),
                eq("AI_PROVIDER_ERROR"), eq("蓝图生成失败"), anyLong(), isNull(),
                isNull(), isNull(), isNull(), isNull(), isNull(), isNull(), isNull(), eq(1));
    }

    // ── 收尾与失败 ────────────────────────────────────────────────────────

    /** 还有没写完的分段就不定稿：定稿会把半篇正文冻结、排版、交付。 */
    @Test
    void completeRefusesWhileAnyUnitIsUnfinished() {
        when(productionRepository.listGenerationUnits(TASK)).thenReturn(List.of(unit("u1", "SUCCEEDED"), unit("u2", "FAILED")));

        IllegalStateException failure = catchThrowableOfType(IllegalStateException.class,
                () -> service.complete(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH));

        assertThat(failure).hasMessage("正文任务仍有未完成分段");
        verifyNoInteractions(finalizationService);
    }

    @Test
    void completeHandsFinishedAndSkippedUnitsToFinalization() {
        List<BidGenerationUnit> units = List.of(unit("u1", "SUCCEEDED"), unit("u2", "SKIPPED"));
        when(productionRepository.listGenerationUnits(TASK)).thenReturn(units);

        service.complete(TASK, BID, OWNER, "snap-1", SNAPSHOT_HASH);

        verify(finalizationService).complete(TASK, OWNER, snapshot, units);
    }

    /** 任务失败原因截到 500 字写进任务；空白原因给出通用说明；任务已经不在进行中时不补事件。 */
    @Test
    void failRecordsATruncatedReasonAndOnlyLogsWhenTheTaskWasStillRunning() {
        String longReason = "失".repeat(600);
        when(bidRepository.failGenerationTask(TASK, BID, "失".repeat(500))).thenReturn(true);
        when(bidRepository.failGenerationTask(TASK, BID, "正文生成失败")).thenReturn(false);

        service.fail(TASK, BID, longReason);
        service.fail(TASK, BID, "  ");

        verify(productionRepository).appendEvent(TASK, BID, null, "TASK_FAILED", longReason);
        verify(productionRepository, never()).appendEvent(TASK, BID, null, "TASK_FAILED", "正文生成失败");
    }

    @Test
    void reviewNowIsTheReviewService() {
        service.reviewNow(BID, OWNER, "req-9");

        verify(reviewService).reviewNow(BID, OWNER, "req-9");
    }

    // ── 构造 ─────────────────────────────────────────────────────────────

    /** 一个可以领取、可以写的单元：领取成功后重新读到的是运行中的它。 */
    private BidGenerationUnit claimable(String id, int wordBudget) {
        BidGenerationUnit running = unit(id, "RUNNING", wordBudget);
        when(productionRepository.findGenerationUnit(id)).thenReturn(Optional.of(unit(id, "PENDING", wordBudget)), Optional.of(running));
        when(draftFactory.outlineForChapter(snapshot, "c1")).thenReturn(outline("PENDING"));
        when(productionRepository.startGenerationUnit(id)).thenReturn(true);
        when(productionRepository.listGenerationUnits(TASK)).thenReturn(List.of(running));
        when(blueprintService.resolve(snapshot, running)).thenReturn(blueprint);
        when(draftFactory.create(snapshot, running, List.of(running), blueprint)).thenReturn(draftRequest);
        when(productionRepository.beginAiRun(any())).thenReturn(new BidProductionRepository.AiRunHandle("run-1", "attempt-1", "RUNNING", 1));
        when(draftFactory.assembleChapter(eq(List.of(running)), eq(running), anyString())).thenReturn("<p>组装后的总体设计</p>");
        when(draftFactory.chapterSummary(List.of(running), running, "本段摘要")).thenReturn("章节摘要");
        return running;
    }

    private record GeneratedCommit(BidProductionRepository.GeneratedUnitCommit value) {
    }

    private GeneratedCommit committed() {
        ArgumentCaptor<BidProductionRepository.GeneratedUnitCommit> commit =
                ArgumentCaptor.forClass(BidProductionRepository.GeneratedUnitCommit.class);
        verify(productionRepository).completeGeneratedUnit(commit.capture());
        return new GeneratedCommit(commit.getValue());
    }

    private static BidGenerationUnit unit(String id, String status) {
        return unit(id, status, 800);
    }

    private static BidGenerationUnit unit(String id, String status, int wordBudget) {
        return new BidGenerationUnit(id, TASK, BID, "c1", 1, "总体设计", "idem-" + id, status, 0, wordBudget,
                null, null, null, null, null, NOW);
    }

    private static BidGenerationSnapshot.Outline outline(String status) {
        return new BidGenerationSnapshot.Outline("n1", "c1", status, null, 3, "总体设计", 0, 1, "", List.of(), List.of());
    }

    private static TenderAiGateway.AiResponse<TenderAiGateway.ChapterDraft> response(String html) {
        return new TenderAiGateway.AiResponse<>(
                new TenderAiGateway.ChapterDraft(List.of(), "本段摘要", List.of(), List.of(), List.of(), html),
                new TenderAiGateway.AiDiagnostics("stop", 120, "resp-hash", 1000L, 400L, 50L, 10L, 1));
    }

    private static TenderAiGateway.RevisionCandidate candidate(String html) {
        return new TenderAiGateway.RevisionCandidate(List.of(), "改了", List.of(), List.of(), html);
    }
}
