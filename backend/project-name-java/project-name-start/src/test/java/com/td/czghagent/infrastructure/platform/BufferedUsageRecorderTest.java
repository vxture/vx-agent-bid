// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.platform;

import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.model.UsageEvent;
import com.td.czghagent.domain.model.UsageMetric;
import com.td.czghagent.domain.repository.UsageBufferRepository;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * 什么该被记账，什么不该。
 *
 * <p>这一组的每一条错了都不报错：多记的会变成别人账单上一笔说不清的钱，
 * 少记的是本产品自己少收的钱，而两者都要等到月底对账才浮出来。
 */
class BufferedUsageRecorderTest {

    private final RecordingBuffer buffer = new RecordingBuffer();
    private final Clock clock = Clock.fixed(Instant.parse("2026-09-09T03:00:00Z"), ZoneId.of("UTC"));
    private final BufferedUsageRecorder recorder = new BufferedUsageRecorder(buffer, clock);

    @Test
    void buffersARealWorkspacesUsage() {
        recorder.record(UsageEvent.of(
                new TenantScope("org-1", "ws-1"), UsageMetric.BID_GENERATIONS, "task-9", "user-1"));

        assertThat(buffer.buffered).singleElement().satisfies(event -> {
            assertThat(event.workspaceId()).isEqualTo("ws-1");
            assertThat(event.metric()).isEqualTo(UsageMetric.BID_GENERATIONS);
            assertThat(event.amount()).isEqualTo(1);
            assertThat(event.endUserId()).isEqualTo("user-1");
        });
    }

    /**
     * 过渡租户的用量<strong>不上报</strong>。
     *
     * <p>本地账号的 workspace 是 {@code local:<用户id>}，平台那边不存在这个空间。
     * 报上去不会失败——平台照收，然后这些数字落进一个没有主人的空间：
     * 不出现在任何账单里，只是把对账弄脏。而这个错误<strong>只会在切到平台身份
     * 之前发生</strong>，也就是没人盯着账单的那段时间。
     */
    @Test
    void refusesToBillAPlaceholderWorkspace() {
        recorder.record(UsageEvent.of(
                TenantScope.local("user-1"), UsageMetric.DOCUMENT_EXPORTS, "export-1", "user-1"));

        assertThat(buffer.buffered).isEmpty();
    }

    @Test
    void refusesWithoutAWorkspaceAtAll() {
        recorder.record(UsageEvent.of(null, UsageMetric.DOCUMENT_EXPORTS, "export-1", "user-1"));

        assertThat(buffer.buffered).isEmpty();
    }

    /** 0 或负数是调用方的 bug，不是「这次不计量」的写法——记下去会让账变成负的。 */
    @Test
    void refusesNonPositiveAmounts() {
        recorder.record(new UsageEvent("ws-1", UsageMetric.BID_GENERATIONS, 0, "k1", null, null));
        recorder.record(new UsageEvent("ws-1", UsageMetric.BID_GENERATIONS, -5, "k2", null, null));

        assertThat(buffer.buffered).isEmpty();
    }

    @Test
    void refusesWithoutAnIdempotencyKey() {
        recorder.record(new UsageEvent("ws-1", UsageMetric.BID_GENERATIONS, 1, "  ", null, null));

        assertThat(buffer.buffered).isEmpty();
    }

    /**
     * 缓冲失败绝不能冒泡到调用方。
     *
     * <p>调用点在导出和生成的成功路径上。让计量的一次数据库抖动去掀翻一份
     * 已经产出的成果，是拿用户的工作去换一条记账——而那条账本来就可以补。
     */
    @Test
    void neverLetsAMeteringFailureReachTheCaller() {
        BufferedUsageRecorder failing = new BufferedUsageRecorder(new UsageBufferRepository() {
            @Override
            public void buffer(UsageEvent event, LocalDateTime occurredAt) {
                throw new IllegalStateException("database is on fire");
            }

            @Override
            public List<BufferedUsage> claim(String t, int l, LocalDateTime n, LocalDateTime e) {
                return List.of();
            }

            @Override
            public void markFlushed(Map<String, String> platformEventIds, LocalDateTime at) {
            }

            @Override
            public void release(List<String> keys, String reason) {
            }

            @Override
            public int purgeFlushedBefore(LocalDateTime before) {
                return 0;
            }

            @Override
            public long countUnflushed() {
                return 0;
            }
        }, clock);

        assertThatCode(() -> failing.record(UsageEvent.of(
                new TenantScope("org-1", "ws-1"), UsageMetric.DOCUMENT_EXPORTS, "e-1", "u-1")))
                .doesNotThrowAnyException();
    }

    /** 幂等键由业务标识组成，不是随机数——重放才可能被识别出来。 */
    @Test
    void derivesTheIdempotencyKeyFromTheThingBeingMetered() {
        UsageEvent first = UsageEvent.of(
                new TenantScope("o", "ws-1"), UsageMetric.DOCUMENT_EXPORTS, "export-7", "u");
        UsageEvent again = UsageEvent.of(
                new TenantScope("o", "ws-1"), UsageMetric.DOCUMENT_EXPORTS, "export-7", "u");

        assertThat(first.idempotencyKey()).isEqualTo(again.idempotencyKey());
        assertThat(first.idempotencyKey())
                .as("键上带指标名，两个指标撞上同一个实体 id 也不会互相顶掉")
                .isEqualTo("tenderforge.document.exports:export-7");
    }

    private static final class RecordingBuffer implements UsageBufferRepository {
        private final List<UsageEvent> buffered = new ArrayList<>();

        @Override
        public void buffer(UsageEvent event, LocalDateTime occurredAt) {
            buffered.add(event);
        }

        @Override
        public List<BufferedUsage> claim(String t, int l, LocalDateTime n, LocalDateTime e) {
            return List.of();
        }

        @Override
        public void markFlushed(Map<String, String> platformEventIds, LocalDateTime at) {
        }

        @Override
        public void release(List<String> keys, String reason) {
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
}
