// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.model.ProvisioningEvent;
import com.td.czghagent.domain.repository.ProvisioningRepository;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;

/**
 * C3 下发的 JDBC 实现。
 */
@Repository
public class JdbcProvisioningRepository implements ProvisioningRepository {

    private final JdbcTemplate jdbcTemplate;

    public JdbcProvisioningRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 用主键冲突做幂等闸门。
     *
     * <p>「先查有没有、没有就插」在两个副本之间有一条缝：两边都查到没有，
     * 于是同一个开通事件被处理两遍。改成直接插、撞了就认输，那条缝在数据库
     * 层面就不存在——这不是优化，是这段逻辑<strong>唯一</strong>正确的写法。
     */
    @Override
    public boolean claimDelivery(String deliveryId, String eventType, String workspaceId,
                                 long seq, LocalDateTime receivedAt) {
        try {
            jdbcTemplate.update("""
                    INSERT INTO platform_provision_delivery(
                        delivery_id, event_type, workspace_id, seq, outcome, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """, deliveryId, eventType, workspaceId, seq, "RECEIVED", receivedAt);
            return true;
        } catch (DuplicateKeyException alreadySeen) {
            return false;
        }
    }

    @Override
    public void recordOutcome(String deliveryId, String outcome) {
        jdbcTemplate.update(
                "UPDATE platform_provision_delivery SET outcome = ? WHERE delivery_id = ?",
                outcome, deliveryId);
    }

    @Override
    public long lastSeq(String workspaceId, String product) {
        Long seq = jdbcTemplate.query("""
                SELECT last_seq FROM platform_workspace_provision
                WHERE workspace_id = ? AND product = ?
                """, rs -> rs.next() ? rs.getLong("last_seq") : null, workspaceId, product);
        // 没有记录时返回 0 而不是 -1：seq 从 1 开始，0 表示「还没处理过任何一条」。
        return seq == null ? 0L : seq;
    }

    /**
     * 落地状态并推进 seq。
     *
     * <p>先 UPDATE 后 INSERT，而不是 upsert 语法。写成这样最初是为了兼容 H2；
     * 引擎统一到 Postgres 之后 {@code ON CONFLICT DO UPDATE} 已经可用，但这段
     * 逻辑的并发正确性是被竞态测试逐条验过的，换写法要连那些验证一起重做。
     * 保持现状不是惯性——是「已验证过的东西不因为有更漂亮的写法就重写」。
     *
     * <p>UPDATE 带上 {@code last_seq < ?} 是第二道顺序闸门。调用方已经比过一次
     * seq，但那之后到这里之间另一个副本可能刚写完一条更新的——带上这个条件，
     * 一条旧事件在数据库层面也无法把状态改回去。
     */
    @Override
    public void upsertInstance(String workspaceId, String product, String state,
                               long seq, LocalDateTime at) {
        String timestampColumn = ProvisioningEvent.STATE_PROVISIONED.equals(state)
                ? "provisioned_at" : "deprovisioned_at";
        int updated = jdbcTemplate.update("""
                UPDATE platform_workspace_provision
                SET state = ?, last_seq = ?, %s = ?, updated_at = ?
                WHERE workspace_id = ? AND product = ? AND last_seq < ?
                """.formatted(timestampColumn),
                state, seq, at, at, workspaceId, product, seq);
        if (updated > 0) {
            return;
        }
        try {
            jdbcTemplate.update("""
                    INSERT INTO platform_workspace_provision(
                        workspace_id, product, state, last_seq, %s, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """.formatted(timestampColumn),
                    workspaceId, product, state, seq, at, at);
        } catch (DuplicateKeyException raced) {
            // 行已存在但 UPDATE 没命中，说明另一个副本刚写入了 seq 不更小的状态。
            // 它赢了，这条就此作废——这正是 last_seq 条件要保护的结果。
        }
    }
}
