// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.domain.repository;

import java.time.LocalDateTime;

/**
 * C3 下发的落库口。
 */
public interface ProvisioningRepository {

    /**
     * 抢占一次投递。
     *
     * <p>返回 {@code true} 表示这是第一次见到它，可以往下处理；{@code false} 表示重复投递。
     *
     * <p>刻意做成「抢占」而不是「先查后插」：平台只保证至少一次，重复投递
     * <strong>一定</strong>会发生，而且可能并发到达。先查后插之间那条缝会让
     * 同一个事件被处理两遍——用主键冲突来判，那条缝就不存在。
     */
    boolean claimDelivery(String deliveryId, String eventType, String workspaceId,
                          long seq, LocalDateTime receivedAt);

    /** 记下这次投递的处置结果，供对账。 */
    void recordOutcome(String deliveryId, String outcome);

    /** 该空间已处理到的最大 seq；没有记录时返回 0。 */
    long lastSeq(String workspaceId, String product);

    /**
     * 落地开通状态并推进 seq。
     *
     * <p>停用是<strong>归档</strong>：只改状态、记时间，绝不删数据。
     * 平台可能在停用后重新开通，而那时用户期望自己的标书还在。
     */
    void upsertInstance(String workspaceId, String product, String state,
                        long seq, LocalDateTime at);
}
