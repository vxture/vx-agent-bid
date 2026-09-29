// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.platform;

import com.td.czghagent.domain.model.Entitlement;
import com.td.czghagent.domain.model.UsageEvent;
import com.td.czghagent.domain.port.EntitlementResolver;
import com.td.czghagent.domain.port.UsageConsumeClient;
import com.td.czghagent.domain.repository.UsageBufferRepository;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * 冲洗任务：把缓冲区里的用量交给平台，并处理平台的回答。
 *
 * <p>这里最容易接反的是 <strong>consume 永远答 200</strong> 这一条。
 * 把 {@code gated} 当成拒绝去处理，产品就替平台裁决了一次配额——
 * 而平台的语义是「记录，不裁决」。接反之后那条用量会永远留在缓冲区里被重报：
 * 平台每次都记下（幂等键让它无操作），产品每次都认为没成功，缓冲区永远清不空。
 */
class UsageFlushJobTest {

    private static final Clock CLOCK =
            Clock.fixed(Instant.parse("2026-09-09T03:00:00Z"), ZoneId.of("UTC"));

    private final FakeBuffer buffer = new FakeBuffer();
    private final RecordingResolver entitlements = new RecordingResolver();

    // ── 永远 200 ────────────────────────────────────────────────────────────

    /** {@code gated: true} 是<strong>已记下</strong>，不是失败。 */
    @Test
    void treatsAGatedResponseAsRecordedNotRejected() {
        buffer.rows.add(row("k1", "ws-1"));

        UsageFlushJob.Summary summary = job(usage -> gated()).flushOnce();

        assertThat(summary.recorded()).isEqualTo(1);
        assertThat(summary.retried()).isZero();
        assertThat(summary.gated()).isEqualTo(1);
        assertThat(buffer.flushed).containsExactly("k1");
        assertThat(buffer.released).isEmpty();
    }

    /**
     * gated 立刻驱逐该空间的权益缓存——这是 C2 失效链的一端。
     *
     * <p>不接的表现：用户用超配额后，界面还会有最长 45 秒显示「余量充足」，
     * 而那几十秒正是他盯着屏幕想弄明白为什么点不动的时候。
     */
    @Test
    void closesTheInvalidationChainWhenTheQuotaDidNotCover() {
        buffer.rows.add(row("k1", "ws-1"));
        buffer.rows.add(row("k2", "ws-1"));
        buffer.rows.add(row("k3", "ws-2"));

        job(usage -> "ws-2".equals(usage.workspaceId()) ? recorded() : gated()).flushOnce();

        assertThat(entitlements.invalidated)
                .as("被 gate 的空间要驱逐，没被 gate 的不该白白丢掉缓存")
                .containsExactly("ws-1");
    }

    @Test
    void countsAnIdempotentReplayWithoutTreatingItAsNew() {
        buffer.rows.add(row("k1", "ws-1"));

        UsageFlushJob.Summary summary = job(usage ->
                new UsageConsumeClient.Outcome(200, false, true, "evt-original", null)).flushOnce();

        assertThat(summary.replayed()).isEqualTo(1);
        assertThat(summary.recorded()).isEqualTo(1);
    }

    /**
     * 记下平台给每一行的事件 id——重放时是原始事件的那个。
     *
     * <p>丢掉它不报错：缓冲区照样清空，只是对账时两侧只能拿幂等键去模糊对，
     * 而平台侧查一条事件要的正是这个 id（通则 C3 上行）。
     */
    @Test
    void keepsThePlatformEventIdOfEveryRecordedRowIncludingReplays() {
        buffer.rows.add(row("fresh", "ws-1"));
        buffer.rows.add(row("again", "ws-1"));
        buffer.rows.add(row("down", "ws-1"));

        job(usage -> switch (usage.idempotencyKey()) {
            case "fresh" -> new UsageConsumeClient.Outcome(200, false, false, "evt-new", null);
            case "again" -> new UsageConsumeClient.Outcome(200, false, true, "evt-original", null);
            default -> new UsageConsumeClient.Outcome(503, false, false, null, "upstream down");
        }).flushOnce();

        assertThat(buffer.eventIds)
                .as("没记下的行没有事件 id，也不该出现在这里")
                .containsExactly(Map.entry("fresh", "evt-new"), Map.entry("again", "evt-original"));
    }

    // ── 非 200 留在缓冲区 ───────────────────────────────────────────────────

    /**
     * 非 200 = 还没记下，行留着重试。
     *
     * <p>标成已冲洗才是真正的丢账：那笔钱再也不会被上报，而缓冲区看起来很干净。
     */
    @Test
    void leavesAnUnrecordedRowBufferedForTheNextRound() {
        buffer.rows.add(row("k1", "ws-1"));

        UsageFlushJob.Summary summary = job(usage ->
                new UsageConsumeClient.Outcome(503, false, false, null, "upstream down")).flushOnce();

        assertThat(summary.retried()).isEqualTo(1);
        assertThat(summary.recorded()).isZero();
        assertThat(buffer.flushed).isEmpty();
        assertThat(buffer.released).containsExactly("k1");
        assertThat(buffer.lastReleaseReason).contains("503").contains("upstream down");
    }

    /** 一条失败不该让同一批里其它成功的也退回去。 */
    @Test
    void keepsTheSuccessesWhenOneRowInTheBatchFails() {
        buffer.rows.add(row("ok-1", "ws-1"));
        buffer.rows.add(row("bad", "ws-1"));
        buffer.rows.add(row("ok-2", "ws-1"));

        job(usage -> "bad".equals(usage.idempotencyKey())
                ? new UsageConsumeClient.Outcome(500, false, false, null, "boom")
                : recorded()).flushOnce();

        assertThat(buffer.flushed).containsExactlyInAnyOrder("ok-1", "ok-2");
        assertThat(buffer.released).containsExactly("bad");
    }

    /**
     * 归还认领必须发生，否则失败的行要等一整个租约（5 分钟）才被重试。
     *
     * <p>平台的一次 502 通常几秒就过去了，让用量为此多等五分钟没有道理。
     */
    @Test
    void handsTheClaimBackSoARetryDoesNotWaitOutTheWholeLease() {
        buffer.rows.add(row("k1", "ws-1"));

        job(usage -> new UsageConsumeClient.Outcome(0, false, false, null, "connection refused"))
                .flushOnce();

        assertThat(buffer.released).containsExactly("k1");
    }

    // ── 顺序与健壮性 ────────────────────────────────────────────────────────

    /**
     * 先记账，再驱逐缓存。
     *
     * <p>反过来的话，驱逐时的一次异常会让已经上报成功的行没被标记，
     * 下一轮再报一次——幂等键保住了钱，但缓冲区里会留下一批永远标不掉的行。
     */
    @Test
    void marksTheLedgerBeforeTouchingTheCache() {
        buffer.rows.add(row("k1", "ws-1"));
        entitlements.explodeOnInvalidate = true;

        assertThatCode(() -> job(usage -> gated()).flushOnce()).doesNotThrowAnyException();
        assertThat(buffer.flushed).as("驱逐炸了，账仍然记住了").containsExactly("k1");
    }

    /**
     * 一轮里的任何异常都不许逃出去。
     *
     * <p>它跑在调度线程上，而用量停止上报本身不会有任何告警——
     * 一个穿过调度器的异常只会进日志，然后没人看见。
     */
    @Test
    void survivesAStoreThatThrows() {
        buffer.explodeOnClaim = true;

        UsageFlushJob.Summary summary = job(usage -> recorded()).flushOnce();

        assertThat(summary.claimed()).isZero();
    }

    @Test
    void doesNotCallThePlatformWhenThereIsNothingBuffered() {
        List<String> calls = new ArrayList<>();

        UsageFlushJob.Summary summary = job(usage -> {
            calls.add(usage.idempotencyKey());
            return recorded();
        }).flushOnce();

        assertThat(calls).isEmpty();
        assertThat(summary.claimed()).isZero();
    }

    /** 每轮一个新的认领令牌——复用会让上一轮遗留的行被当成这一轮认领到的。 */
    @Test
    void usesAFreshClaimTokenEveryRound() {
        buffer.rows.add(row("k1", "ws-1"));
        UsageFlushJob job = job(usage -> recorded());

        job.flushOnce();
        buffer.rows.add(row("k2", "ws-1"));
        job.flushOnce();

        assertThat(buffer.claimTokens).hasSize(2);
        assertThat(buffer.claimTokens.get(0)).isNotEqualTo(buffer.claimTokens.get(1));
    }

    // ── 辅助 ────────────────────────────────────────────────────────────────

    private UsageFlushJob job(
            Function<UsageBufferRepository.BufferedUsage, UsageConsumeClient.Outcome> answer) {
        return new UsageFlushJob(buffer, new UsageConsumeClient() {
            @Override
            public Outcome consume(UsageBufferRepository.BufferedUsage usage) {
                return answer.apply(usage);
            }

            @Override
            public boolean isMock() {
                return true;
            }
        }, entitlements, 100, CLOCK);
    }

    private static UsageConsumeClient.Outcome recorded() {
        return new UsageConsumeClient.Outcome(200, false, false, "evt", null);
    }

    private static UsageConsumeClient.Outcome gated() {
        return new UsageConsumeClient.Outcome(200, true, false, "evt", "pool exhausted");
    }

    private static UsageBufferRepository.BufferedUsage row(String key, String workspaceId) {
        return new UsageBufferRepository.BufferedUsage(
                key, workspaceId, "tenderforge.bid.generations", 1,
                "user-1", null, LocalDateTime.parse("2026-09-09T10:00:00"), 0);
    }

    private static final class FakeBuffer implements UsageBufferRepository {
        private final List<BufferedUsage> rows = new ArrayList<>();
        private final List<String> flushed = new ArrayList<>();
        private final Map<String, String> eventIds = new LinkedHashMap<>();
        private final List<String> released = new ArrayList<>();
        private final List<String> claimTokens = new ArrayList<>();
        private String lastReleaseReason;
        private boolean explodeOnClaim;

        @Override
        public void buffer(UsageEvent event, LocalDateTime occurredAt) {
        }

        @Override
        public List<BufferedUsage> claim(String claimToken, int limit,
                                         LocalDateTime now, LocalDateTime lease) {
            if (explodeOnClaim) {
                throw new IllegalStateException("claim failed");
            }
            claimTokens.add(claimToken);
            List<BufferedUsage> claimed = List.copyOf(rows);
            rows.clear();
            return claimed;
        }

        @Override
        public void markFlushed(Map<String, String> platformEventIds, LocalDateTime at) {
            flushed.addAll(platformEventIds.keySet());
            eventIds.putAll(platformEventIds);
        }

        @Override
        public void release(List<String> keys, String reason) {
            released.addAll(keys);
            if (!keys.isEmpty()) {
                lastReleaseReason = reason;
            }
        }

        @Override
        public int purgeFlushedBefore(LocalDateTime before) {
            return 0;
        }

        @Override
        public long countUnflushed() {
            return 0;
        }
    }

    private static final class RecordingResolver implements EntitlementResolver {
        private final List<String> invalidated = new ArrayList<>();
        private boolean explodeOnInvalidate;

        @Override
        public Entitlement resolve(String workspaceId) {
            return Entitlement.none(workspaceId, "tenderforge");
        }

        @Override
        public void invalidate(String workspaceId) {
            invalidated.add(workspaceId);
            if (explodeOnInvalidate) {
                throw new IllegalStateException("cache is on fire");
            }
        }

        @Override
        public boolean isMock() {
            return true;
        }
    }
}
