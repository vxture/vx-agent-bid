// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.model.AuditEvent;
import com.td.czghagent.domain.model.Entitlement;
import com.td.czghagent.domain.model.ProvisioningEvent;
import com.td.czghagent.domain.port.EntitlementResolver;
import com.td.czghagent.domain.repository.AuditRepository;
import com.td.czghagent.domain.repository.ProvisioningRepository;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * 开通/停用事件的处理。
 *
 * <p>平台只保证至少一次投递，所以重复与乱序<strong>一定</strong>会发生。
 * 这一组的每一条错了都不会抛异常：要么某个空间的开通状态被一条迟到的旧事件
 * 改回去，要么同一个事件的副作用跑了两遍，要么平台开始无限重试一件已经办好的事。
 */
class ProvisioningCommandServiceTest {

    private static final LocalDateTime NOW = LocalDateTime.parse("2026-09-09T10:00:00");
    private static final String WS = "ws-1";

    private final FakeRepository repository = new FakeRepository();
    private final RecordingResolver entitlements = new RecordingResolver();
    private final List<AuditEvent> audits = new ArrayList<>();
    private final ProvisioningCommandService service = new ProvisioningCommandService(
            repository, entitlements, audits::add);

    // ── 正常处理 ────────────────────────────────────────────────────────────

    @Test
    void recordsAProvisionedWorkspaceAndRefreshesItsEntitlement() {
        ProvisioningCommandService.Outcome outcome =
                service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);

        assertThat(outcome).isEqualTo(ProvisioningCommandService.Outcome.PROCESSED);
        assertThat(repository.state).isEqualTo(ProvisioningEvent.STATE_PROVISIONED);
        assertThat(repository.lastSeq).isEqualTo(1);
        assertThat(entitlements.invalidated)
                .as("开通就是权益变更——不驱逐的话用户刚买完还要等一个 TTL")
                .containsExactly(WS);
    }

    /**
     * 停用是<strong>改状态</strong>，不是删数据。
     *
     * <p>平台可能在停用后重新开通，而那时用户期望自己的标书还在。
     * 一个在停用事件里做硬删除的产品，会把一次账务操作变成不可逆的数据丢失。
     */
    @Test
    void archivesOnDeprovisionInsteadOfDestroyingAnything() {
        service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);
        service.handle(event("d-2", ProvisioningEvent.DEPROVISIONED, 2), "trace-2", NOW);

        assertThat(repository.state).isEqualTo(ProvisioningEvent.STATE_DEPROVISIONED);
        assertThat(repository.deleted).as("这个口上根本没有删除操作").isFalse();
        assertThat(entitlements.invalidated).containsExactly(WS, WS);
    }

    /** 审计的发起人是平台，且带上投递标识，好和平台侧的投递记录对上。 */
    @Test
    void auditsThePlatformAsTheActorAndKeepsTheDeliveryId() {
        service.handle(event("d-77", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);

        assertThat(audits).singleElement().satisfies(audit -> {
            assertThat(audit.actorId()).isEqualTo("platform");
            assertThat(audit.actorConsole())
                    .as("平台发起的动作没有本产品控制台，编一个会污染按控制台的筛查")
                    .isNull();
            assertThat(audit.detailSummary()).contains("d-77");
            assertThat(audit.objectId()).isEqualTo(WS);
        });
    }

    // ── 至少一次投递的正常产物 ──────────────────────────────────────────────

    /**
     * 重复投递不再跑一遍副作用。
     *
     * <p>「至少一次」意味着同一条会来两次。第二次再 upsert 一遍状态本身无害，
     * 但审计会多一条、驱逐会多一次——而更要紧的是，一旦以后这里挂上了
     * 「开通时初始化业务空间」，重复执行就不再无害了。
     */
    @Test
    void runsTheSideEffectsOnlyOnceForARepeatedDelivery() {
        service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);
        ProvisioningCommandService.Outcome second =
                service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);

        assertThat(second).isEqualTo(ProvisioningCommandService.Outcome.DUPLICATE);
        assertThat(audits).hasSize(1);
        assertThat(entitlements.invalidated).hasSize(1);
    }

    /**
     * 迟到的旧事件不能把状态改回去。
     *
     * <p>这是乱序投递最贵的一种表现：一次网络抖动让 seq=1 的开通事件排在
     * seq=2 的停用之后到达，于是一个已经停用的空间被改回开通——
     * 而这不会报错，只会让账和事实分叉。
     */
    @Test
    void refusesToLetAStaleEventRewriteANewerState() {
        service.handle(event("d-2", ProvisioningEvent.DEPROVISIONED, 2), "trace-2", NOW);

        ProvisioningCommandService.Outcome late =
                service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1), "trace-1", NOW);

        assertThat(late).isEqualTo(ProvisioningCommandService.Outcome.STALE);
        assertThat(repository.state)
                .as("停用了就是停用了，一条迟到的开通不能翻案")
                .isEqualTo(ProvisioningEvent.STATE_DEPROVISIONED);
        assertThat(entitlements.invalidated).hasSize(1);
    }

    /** 相同 seq 也算过期——重发不该被当成一次新的状态变更。 */
    @Test
    void treatsAReplayedSequenceNumberAsStale() {
        service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 5), "trace-1", NOW);

        assertThat(service.handle(event("d-2", ProvisioningEvent.PROVISIONED, 5), "trace-2", NOW))
                .isEqualTo(ProvisioningCommandService.Outcome.STALE);
    }

    /**
     * 没见过的事件类型：记下投递、不做动作。
     *
     * <p>报错的表现是平台把一个我们本来就不关心的事件重试到天荒地老。
     * 平台加一个新事件类型是一次对它完全正常的变更。
     */
    @Test
    void recordsAnUnknownEventTypeWithoutActingOnIt() {
        ProvisioningCommandService.Outcome outcome =
                service.handle(event("d-1", "tenant.renamed", 1), "trace-1", NOW);

        assertThat(outcome).isEqualTo(ProvisioningCommandService.Outcome.UNKNOWN_TYPE);
        assertThat(repository.claimed).contains("d-1");
        assertThat(repository.state).isNull();
        assertThat(entitlements.invalidated).isEmpty();
    }

    /** 发给别的产品的事件，连投递都不该记——它不是我们的账。 */
    @Test
    void ignoresAnEventAddressedToAnotherProduct() {
        ProvisioningCommandService.Outcome outcome = service.handle(
                new ProvisioningEvent("d-1", ProvisioningEvent.PROVISIONED, 1,
                        WS, "org-1", "some-other-product"),
                "trace-1", NOW);

        assertThat(outcome).isEqualTo(ProvisioningCommandService.Outcome.WRONG_PRODUCT);
        assertThat(repository.claimed).isEmpty();
        assertThat(entitlements.invalidated).isEmpty();
    }

    // ── 通知类事件 ──────────────────────────────────────────────────────────

    /**
     * 套餐变更通知不带 seq，也必须让权益缓存失效。
     *
     * <p>按 seq=0 做乱序判定，它在任何开通过（seq≥1）的空间上都是「过期」——
     * 于是用户升了档，界面还按旧档位渲染，而这一路没有任何报错。
     */
    @Test
    void aSubscriptionChangeWithoutSeqStillEvictsTheEntitlementOfAProvisionedWorkspace() {
        service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 3), "trace-1", NOW);

        ProvisioningCommandService.Outcome outcome = service.handle(
                event("d-2", ProvisioningEvent.SUBSCRIPTION_CHANGED, 0), "trace-2", NOW);

        assertThat(outcome).isEqualTo(ProvisioningCommandService.Outcome.NOTIFIED);
        assertThat(entitlements.invalidated)
                .as("开通一次、套餐变更一次，各驱逐一次")
                .containsExactly(WS, WS);
        assertThat(repository.lastSeq).as("通知不推进开通序号").isEqualTo(3);
        assertThat(repository.state).isEqualTo(ProvisioningEvent.STATE_PROVISIONED);
    }

    /** 授权失效通知：本产品不持有共享授权缓存，记下投递、不碰开通状态与权益缓存。 */
    @Test
    void acknowledgesAGrantInvalidationWithoutTouchingProvisioningState() {
        ProvisioningCommandService.Outcome outcome = service.handle(
                event("d-1", ProvisioningEvent.GRANT_INVALIDATED, 0), "trace-1", NOW);

        assertThat(outcome).isEqualTo(ProvisioningCommandService.Outcome.NOTIFIED);
        assertThat(repository.claimed).contains("d-1");
        assertThat(repository.state).isNull();
        assertThat(entitlements.invalidated).isEmpty();
    }

    /** 通知同样至少一次投递：重投不再驱逐一遍。 */
    @Test
    void aRepeatedNotificationIsHandledOnlyOnce() {
        service.handle(event("d-1", ProvisioningEvent.SUBSCRIPTION_CHANGED, 0), "trace-1", NOW);

        assertThat(service.handle(
                event("d-1", ProvisioningEvent.SUBSCRIPTION_CHANGED, 0), "trace-1", NOW))
                .isEqualTo(ProvisioningCommandService.Outcome.DUPLICATE);
        assertThat(entitlements.invalidated).hasSize(1);
    }

    // ── 健壮性 ──────────────────────────────────────────────────────────────

    /**
     * 驱逐失败不能把一次处理成功的投递变成失败。
     *
     * <p>接收端把异常翻译成 500，而平台会永远重试 500。
     * 漏一次驱逐最多让档位陈旧 45 秒；一场重试风暴的代价大得多。
     */
    @Test
    void doesNotFailADeliveryJustBecauseTheCacheEvictionDid() {
        entitlements.explode = true;

        assertThatCode(() ->
                assertThat(service.handle(event("d-1", ProvisioningEvent.PROVISIONED, 1),
                        "trace-1", NOW))
                        .isEqualTo(ProvisioningCommandService.Outcome.PROCESSED))
                .doesNotThrowAnyException();
        assertThat(repository.state).isEqualTo(ProvisioningEvent.STATE_PROVISIONED);
    }

    // ── 辅助 ────────────────────────────────────────────────────────────────

    private static ProvisioningEvent event(String deliveryId, String type, long seq) {
        return new ProvisioningEvent(deliveryId, type, seq, WS, "org-1", "tenderforge");
    }

    private static final class FakeRepository implements ProvisioningRepository {
        private final Set<String> claimed = new LinkedHashSet<>();
        private String state;
        private long lastSeq;
        private boolean deleted;

        @Override
        public boolean claimDelivery(String deliveryId, String eventType, String workspaceId,
                                     long seq, LocalDateTime receivedAt) {
            return claimed.add(deliveryId);
        }

        @Override
        public void recordOutcome(String deliveryId, String outcome) {
        }

        @Override
        public long lastSeq(String workspaceId, String product) {
            return lastSeq;
        }

        @Override
        public void upsertInstance(String workspaceId, String product, String state,
                                   long seq, LocalDateTime at) {
            this.state = state;
            this.lastSeq = seq;
        }
    }

    private static final class RecordingResolver implements EntitlementResolver {
        private final List<String> invalidated = new ArrayList<>();
        private boolean explode;

        @Override
        public Entitlement resolve(String workspaceId) {
            return Entitlement.none(workspaceId, "tenderforge");
        }

        @Override
        public void invalidate(String workspaceId) {
            invalidated.add(workspaceId);
            if (explode) {
                throw new IllegalStateException("cache is on fire");
            }
        }

        @Override
        public boolean isMock() {
            return true;
        }
    }
}
