// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.model.UsageEvent;
import com.td.czghagent.domain.repository.UsageBufferRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 用量缓冲区的 JDBC 实现。
 */
@Repository
public class JdbcUsageBufferRepository implements UsageBufferRepository {

    private static final RowMapper<BufferedUsage> USAGE = (rs, row) -> new BufferedUsage(
            rs.getString("idempotency_key"),
            rs.getString("workspace_id"),
            rs.getString("metric"),
            rs.getLong("amount"),
            rs.getString("end_user_id"),
            rs.getString("task_id"),
            JdbcTimes.localDateTime(rs, "occurred_at"),
            rs.getInt("attempts"));

    private final JdbcTemplate jdbcTemplate;

    public JdbcUsageBufferRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * 写入一条待冲洗的用量。
     *
     * <p>{@code INSERT ... SELECT ... WHERE NOT EXISTS} 而不是 upsert 语法。
     * 写成这样最初是为了兼容 H2；引擎统一到 Postgres 之后 {@code ON CONFLICT}
     * 已经可用，但这段的竞态正确性是被并发测试验过的，换写法要连验证一起重做。
     * 竞态由主键兜底——两个并发插入里输的那个会撞主键，而撞主键正是
     * 「这条已经记过了」的正确答案。
     */
    @Override
    public void buffer(UsageEvent event, LocalDateTime occurredAt) {
        try {
            jdbcTemplate.update("""
                    INSERT INTO platform_usage_event(
                        idempotency_key, workspace_id, metric, amount,
                        end_user_id, task_id, occurred_at
                    )
                    SELECT ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM platform_usage_event WHERE idempotency_key = ?
                    )
                    """,
                    event.idempotencyKey(), event.workspaceId(), event.metric().key(),
                    event.amount(), event.endUserId(), event.taskId(), occurredAt,
                    event.idempotencyKey());
        } catch (org.springframework.dao.DuplicateKeyException duplicate) {
            // 并发下的同键插入。这条用量已经在缓冲区里了，什么也不用做。
        }
    }

    @Override
    public List<BufferedUsage> claim(String claimToken, int limit,
                                     LocalDateTime now, LocalDateTime lease) {
        List<String> candidates = jdbcTemplate.queryForList("""
                SELECT idempotency_key FROM platform_usage_event
                WHERE flushed_at IS NULL
                  AND (claimed_at IS NULL OR claimed_at < ?)
                ORDER BY occurred_at
                LIMIT ?
                """, String.class, lease, limit);
        if (candidates.isEmpty()) {
            return List.of();
        }
        // 认领与读回分两步：UPDATE 在拿到行锁之后才判 claimed_at，
        // 所以两个节点同时认领时，后到的那个条件不再成立，一行不会被认走两次。
        String placeholders = String.join(",", java.util.Collections.nCopies(candidates.size(), "?"));
        Object[] args = new Object[candidates.size() + 3];
        args[0] = claimToken;
        args[1] = now;
        for (int i = 0; i < candidates.size(); i++) {
            args[i + 2] = candidates.get(i);
        }
        args[args.length - 1] = lease;
        jdbcTemplate.update("""
                UPDATE platform_usage_event
                SET claim_token = ?, claimed_at = ?, attempts = attempts + 1
                WHERE idempotency_key IN (%s)
                  AND flushed_at IS NULL
                  AND (claimed_at IS NULL OR claimed_at < ?)
                """.formatted(placeholders), args);
        return jdbcTemplate.query("""
                SELECT * FROM platform_usage_event
                WHERE claim_token = ? AND flushed_at IS NULL
                ORDER BY occurred_at
                """, USAGE, claimToken);
    }

    @Override
    public void markFlushed(Map<String, String> platformEventIds, LocalDateTime flushedAt) {
        if (platformEventIds.isEmpty()) {
            return;
        }
        // 每行各带自己的平台事件 id，所以是逐行批量更新，不是一条 IN (...)。
        // claim_token 一并清空：它是认领的凭据，冲洗完就不该再有人能按它读到这行。
        List<Object[]> rows = new ArrayList<>();
        platformEventIds.forEach((key, eventId) -> rows.add(new Object[]{flushedAt, eventId, key}));
        jdbcTemplate.batchUpdate("""
                UPDATE platform_usage_event
                SET flushed_at = ?, platform_event_id = ?,
                    claim_token = NULL, claimed_at = NULL, last_error = NULL
                WHERE idempotency_key = ?
                """, rows);
    }

    @Override
    public void release(List<String> idempotencyKeys, String reason) {
        if (idempotencyKeys.isEmpty()) {
            return;
        }
        inChunks(idempotencyKeys, chunk -> jdbcTemplate.update("""
                UPDATE platform_usage_event
                SET claim_token = NULL, claimed_at = NULL, last_error = ?
                WHERE idempotency_key IN (%s)
                """.formatted(placeholders(chunk.size())),
                prepend(truncate(reason), chunk)));
    }

    @Override
    public int purgeFlushedBefore(LocalDateTime before) {
        return jdbcTemplate.update(
                "DELETE FROM platform_usage_event WHERE flushed_at IS NOT NULL AND flushed_at < ?",
                before);
    }

    @Override
    public long countUnflushed() {
        Long count = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM platform_usage_event WHERE flushed_at IS NULL", Long.class);
        return count == null ? 0 : count;
    }

    /** 分块，免得一次冲洗把上千个占位符塞进一条语句里。 */
    private static void inChunks(List<String> keys, java.util.function.Consumer<List<String>> action) {
        for (int start = 0; start < keys.size(); start += 200) {
            action.accept(keys.subList(start, Math.min(start + 200, keys.size())));
        }
    }

    private static String placeholders(int count) {
        return String.join(",", java.util.Collections.nCopies(count, "?"));
    }

    private static Object[] prepend(Object head, List<String> tail) {
        Object[] args = new Object[tail.size() + 1];
        args[0] = head;
        for (int i = 0; i < tail.size(); i++) {
            args[i + 1] = tail.get(i);
        }
        return args;
    }

    /** {@code last_error} 是 512 字符的诊断字段，不是日志——超长就截断，不让一条堆栈把写入打挂。 */
    private static String truncate(String reason) {
        if (reason == null) {
            return null;
        }
        return reason.length() <= 512 ? reason : reason.substring(0, 512);
    }
}
