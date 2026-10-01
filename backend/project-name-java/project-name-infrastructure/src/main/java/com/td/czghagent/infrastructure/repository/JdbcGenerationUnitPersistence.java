// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-28
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.BidGenerationUnit;
import com.td.czghagent.domain.repository.BidProductionRepository;
import java.time.LocalDateTime;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
class JdbcGenerationUnitPersistence {
    private final JdbcTemplate jdbcTemplate;

    JdbcGenerationUnitPersistence(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    List<BidGenerationUnit> list(String taskId) {
        return jdbcTemplate.query("""
                SELECT u.* FROM bid_generation_unit u
                JOIN bid_generation_task t ON t.id = u.task_id
                LEFT JOIN bid_snapshot_outline o
                  ON o.snapshot_id = t.snapshot_id AND o.chapter_id = u.chapter_id
                WHERE u.task_id = ? ORDER BY o.sort_order, u.unit_index, u.id
                """, (rs, row) -> unit(rs), taskId);
    }

    Optional<BidGenerationUnit> find(String unitId) {
        return jdbcTemplate.query("SELECT * FROM bid_generation_unit WHERE id = ?",
                (rs, row) -> unit(rs), unitId).stream().findFirst();
    }

    @Transactional
    boolean start(String unitId) {
        int changed = jdbcTemplate.update("""
                UPDATE bid_generation_unit
                SET status = 'RUNNING', attempt_count = attempt_count + 1,
                    started_at = CURRENT_TIMESTAMP, finished_at = NULL,
                    error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('PENDING', 'FAILED')
                  AND EXISTS(SELECT 1 FROM bid_generation_task t
                      WHERE t.id = bid_generation_unit.task_id AND t.status = 'RUNNING')
                """, unitId);
        if (changed == 0) {
            return false;
        }
        jdbcTemplate.update("""
                UPDATE bid_chapter SET generation_status = CASE
                    WHEN generation_status = 'MANUAL' THEN 'MANUAL' ELSE 'GENERATING' END
                WHERE id = (SELECT chapter_id FROM bid_generation_unit WHERE id = ?)
                """, unitId);
        jdbcTemplate.update("""
                UPDATE bid_generation_task SET heartbeat_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT task_id FROM bid_generation_unit WHERE id = ?)
                """, unitId);
        return true;
    }

    @Transactional
    BidProductionRepository.AiRunHandle begin(BidProductionRepository.AiRunStart run) {
        if (run.generationUnitId() != null) {
            requireTaskRunning(run.taskId());
        }
        Optional<BidProductionRepository.AiRunHandle> existing = findRun(run.idempotencyKey());
        if (existing.isPresent()) {
            BidProductionRepository.AiRunHandle handle = existing.get();
            if ("RUNNING".equals(handle.status()) && run.generationUnitId() == null) {
                throw new BusinessException(
                        "AI_RUN_IN_PROGRESS", "相同输入的AI调用正在执行，请稍后重试", 409);
            }
            if ("RUNNING".equals(handle.status())) {
                interruptAttempt(handle.attemptId(), "AI_RUN_REPLACED",
                        "生成单元恢复后开始新的业务尝试", "STALE_RUNNING_ATTEMPT");
            }
            String attemptId = UUID.randomUUID().toString();
            int attemptNo = handle.attemptCount() + 1;
            jdbcTemplate.update("""
                    UPDATE bid_ai_run SET status = 'RUNNING', attempt_count = attempt_count + 1,
                        object_name = ?, schema_version = ?, error_code = NULL,
                        error_message = NULL, failure_reason = NULL, finished_at = NULL,
                        current_attempt_id = ?
                    WHERE id = ?
                    """, run.objectName(), run.schemaVersion(), attemptId, handle.id());
            insertAttempt(attemptId, handle.id(), attemptNo);
            return new BidProductionRepository.AiRunHandle(
                    handle.id(), attemptId, "RUNNING", attemptNo);
        }
        String attemptId = UUID.randomUUID().toString();
        try {
            jdbcTemplate.update("""
                    INSERT INTO bid_ai_run(
                        id, bid_id, task_id, snapshot_id, generation_unit_id, operation_type,
                        provider, model_name, prompt_version, input_snapshot_hash,
                        idempotency_key, status, object_name, schema_version, attempt_count,
                        current_attempt_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?, ?, 1, ?)
                    """, run.id(), run.bidId(), run.taskId(), run.snapshotId(), run.generationUnitId(),
                    run.operationType(), run.provider(), run.modelName(), run.promptVersion(),
                    run.inputSnapshotHash(), run.idempotencyKey(), run.objectName(),
                    run.schemaVersion(), attemptId);
            insertAttempt(attemptId, run.id(), 1);
            return new BidProductionRepository.AiRunHandle(run.id(), attemptId, "RUNNING", 1);
        } catch (DuplicateKeyException ignored) {
            return begin(run);
        }
    }

    void completeRun(String aiRunId, String attemptId,
                     long durationMillis, Long inputTokens,
                     Long outputTokens, Long reasoningTokens, Long cachedInputTokens,
                     String outputHash, String responseFields,
                     String finishReason, Integer responseLength, String responseHash,
                     Integer attempts, String modelCode) {
        // model_name 在开始时按配置写入；完成时换成实际应答的模型（Atlas 回显，故障转移后是
        // 兜底模型）。没有回显时保留原值——配置名总比空着强，但它不是事实。
        jdbcTemplate.update("""
                UPDATE bid_ai_run SET status = 'SUCCEEDED', duration_ms = ?, input_tokens = ?,
                    model_name = COALESCE(LEFT(?, 100), model_name),
                    output_tokens = ?, reasoning_tokens = ?, cached_input_tokens = ?,
                    output_hash = ?, response_fields = ?, finish_reason = ?,
                    response_length = ?, response_hash = ?,
                    model_attempt_count = COALESCE(?, 1),
                    finished_at = CURRENT_TIMESTAMP,
                    error_code = NULL, error_message = NULL
                    WHERE id = ? AND current_attempt_id = ? AND status = 'RUNNING'
                """, durationMillis, inputTokens, modelCode, outputTokens, reasoningTokens,
                cachedInputTokens, outputHash, responseFields, finishReason, responseLength,
                responseHash, attempts, aiRunId, attemptId);
        completeAttempt(attemptId, durationMillis, inputTokens, outputTokens,
                reasoningTokens, cachedInputTokens, finishReason, responseLength, responseHash, attempts);
    }

    void failRun(String aiRunId, String attemptId,
                 long durationMillis, Long inputTokens, Long outputTokens,
                 Long reasoningTokens, Long cachedInputTokens,
                 String errorCode, String errorMessage,
                 String failureReason, String finishReason, Integer responseLength,
                 String responseHash, Integer attempts) {
        jdbcTemplate.update("""
                UPDATE bid_ai_run SET status = 'FAILED', duration_ms = ?, input_tokens = ?,
                    output_tokens = ?, reasoning_tokens = ?, cached_input_tokens = ?, error_code = ?,
                    error_message = ?, failure_reason = ?, finish_reason = ?, response_length = ?,
                    response_hash = ?, model_attempt_count = COALESCE(?, 1),
                    finished_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND current_attempt_id = ? AND status = 'RUNNING'
                """, durationMillis, inputTokens, outputTokens, reasoningTokens, cachedInputTokens,
                errorCode, limit(errorMessage), diagnostic(failureReason),
                finishReason, responseLength, responseHash, attempts, aiRunId, attemptId);
        failAttempt(attemptId, durationMillis, inputTokens, outputTokens,
                reasoningTokens, cachedInputTokens, errorCode, errorMessage, failureReason,
                finishReason, responseLength, responseHash, attempts);
    }

    @Transactional
    void complete(BidProductionRepository.GeneratedUnitCommit commit) {
        int changed = jdbcTemplate.update("""
                UPDATE bid_generation_unit
                SET status = 'SUCCEEDED', content = ?, content_hash = ?, summary = ?,
                    visible_characters = ?, budget_variance_ratio = ?, budget_status = ?,
                    ai_run_id = ?, error_message = NULL, finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'RUNNING'
                  AND EXISTS(SELECT 1 FROM bid_generation_task t
                      WHERE t.id = bid_generation_unit.task_id AND t.status = 'RUNNING')
                """, commit.unitContent(), commit.unitContentHash(), commit.unitSummary(),
                commit.visibleCharacters(), commit.budgetVarianceRatio(), commit.budgetStatus(),
                commit.aiRunId(), commit.unitId());
        if (changed == 0) {
            markRunInterrupted(commit.aiRunId(), commit.aiRunAttemptId());
            return;
        }
        int chapterChanged = jdbcTemplate.update("""
                UPDATE bid_chapter SET content = ?, generation_status = CASE WHEN EXISTS(
                    SELECT 1 FROM bid_generation_unit u
                    WHERE u.task_id = ? AND u.chapter_id = ?
                      AND u.status NOT IN ('SUCCEEDED', 'SKIPPED')
                ) THEN 'GENERATING' ELSE 'READY' END,
                    updated_at = CURRENT_TIMESTAMP, revision = revision + 1
                WHERE id = ? AND generation_status <> 'MANUAL'
                """, commit.assembledChapterContent(), commit.taskId(), commit.chapterId(), commit.chapterId());
        if (chapterChanged == 1) {
            insertChapterVersion(commit);
        }
        jdbcTemplate.update("""
                UPDATE bid_ai_run SET status = 'SUCCEEDED', duration_ms = ?, input_tokens = ?,
                    model_name = COALESCE(LEFT(?, 100), model_name),
                    output_tokens = ?, reasoning_tokens = ?, cached_input_tokens = ?,
                    output_hash = ?, finish_reason = ?, response_length = ?,
                    response_hash = ?, response_fields = ?,
                    model_attempt_count = COALESCE(?, 1),
                    finished_at = CURRENT_TIMESTAMP,
                    error_code = NULL, error_message = NULL
                    WHERE id = ? AND current_attempt_id = ? AND status = 'RUNNING'
                """, commit.durationMillis(), commit.inputTokens(), commit.modelName(), commit.outputTokens(),
                commit.reasoningTokens(), commit.cachedInputTokens(),
                commit.outputHash(), commit.finishReason(), commit.responseLength(),
                commit.responseHash(), commit.responseFields(), commit.attempts(),
                commit.aiRunId(), commit.aiRunAttemptId());
        completeAttempt(commit.aiRunAttemptId(), commit.durationMillis(), commit.inputTokens(),
                commit.outputTokens(), commit.reasoningTokens(), commit.cachedInputTokens(),
                commit.finishReason(), commit.responseLength(), commit.responseHash(), commit.attempts());
        updateTaskProgress(commit.taskId());
        appendEvent(commit.taskId(), commit.bidId(), commit.chapterId(), "UNIT_SUCCEEDED",
                "已完成《" + commit.unitTitle() + "》分段 " + (commit.unitIndex() + 1));
        if ("OVER_BUDGET".equals(commit.budgetStatus())
                && commit.budgetVarianceRatio() > 0.35d) {
            appendEvent(commit.taskId(), commit.bidId(), commit.chapterId(),
                    "UNIT_OVER_BUDGET_ACCEPTED",
                    "《" + commit.unitTitle() + "》内容超出单元预算，已保存并交由全文篇幅结算");
        }
    }

    void markChapterCompacted(String taskId, String chapterId) {
        jdbcTemplate.update("""
                UPDATE bid_generation_unit
                SET budget_status = 'COMPACTED', compacted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND chapter_id = ? AND status = 'SUCCEEDED'
                """, taskId, chapterId);
    }

    @Transactional
    void skip(String unitId, String taskId, String bidId, String chapterId, String summary) {
        int changed = jdbcTemplate.update("""
                UPDATE bid_generation_unit SET status = 'SKIPPED', summary = ?,
                    error_message = NULL, finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status NOT IN ('SUCCEEDED', 'SKIPPED')
                  AND EXISTS(SELECT 1 FROM bid_generation_task t
                      WHERE t.id = bid_generation_unit.task_id AND t.status = 'RUNNING')
                """, summary, unitId);
        if (changed == 0) {
            return;
        }
        updateTaskProgress(taskId);
        appendEvent(taskId, bidId, chapterId, "UNIT_SKIPPED", "保留人工章节，跳过AI分段");
    }

    @Transactional
    void fail(String unitId, String taskId, String bidId, String chapterId, String aiRunId,
              String aiRunAttemptId, String errorCode, String errorMessage,
              long durationMillis, String failureReason,
              Long inputTokens, Long outputTokens,
              Long reasoningTokens, Long cachedInputTokens,
              String finishReason, Integer responseLength, String responseHash, Integer attempts) {
        String message = limit(errorMessage);
        int changed = jdbcTemplate.update("""
                UPDATE bid_generation_unit SET status = 'FAILED', error_message = ?,
                    finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'RUNNING'
                  AND EXISTS(SELECT 1 FROM bid_generation_task t
                      WHERE t.id = bid_generation_unit.task_id AND t.status = 'RUNNING')
                """, message, unitId);
        if (changed == 0) {
            markRunInterrupted(aiRunId, aiRunAttemptId);
            return;
        }
        jdbcTemplate.update("""
                UPDATE bid_chapter SET generation_status = CASE
                    WHEN generation_status = 'MANUAL' THEN 'MANUAL' ELSE 'FAILED' END
                WHERE id = ?
                """, chapterId);
        if (aiRunId != null) {
            jdbcTemplate.update("""
                    UPDATE bid_ai_run SET status = 'FAILED', duration_ms = ?, input_tokens = ?,
                        output_tokens = ?, reasoning_tokens = ?, cached_input_tokens = ?, error_code = ?,
                        error_message = ?, failure_reason = ?, finish_reason = ?, response_length = ?,
                        response_hash = ?, model_attempt_count = COALESCE(?, 1),
                        finished_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND current_attempt_id = ? AND status = 'RUNNING'
                    """, durationMillis, inputTokens, outputTokens, reasoningTokens,
                    cachedInputTokens, errorCode, message, diagnostic(failureReason), finishReason,
                    responseLength, responseHash, attempts, aiRunId, aiRunAttemptId);
            failAttempt(aiRunAttemptId, durationMillis, inputTokens, outputTokens,
                    reasoningTokens, cachedInputTokens, errorCode, message, failureReason,
                    finishReason, responseLength, responseHash, attempts);
        }
        jdbcTemplate.update("UPDATE bid_generation_task SET heartbeat_at = CURRENT_TIMESTAMP WHERE id = ?", taskId);
        appendEvent(taskId, bidId, chapterId, "UNIT_FAILED", message);
    }

    private void insertChapterVersion(BidProductionRepository.GeneratedUnitCommit commit) {
        Integer latest = jdbcTemplate.queryForObject("""
                SELECT COALESCE(MAX(version_no), 0) FROM bid_chapter_version WHERE chapter_id = ?
                """, Integer.class, commit.chapterId());
        jdbcTemplate.update("""
                INSERT INTO bid_chapter_version(
                    id, bid_id, chapter_id, version_no, source_type, content, content_hash,
                    summary, generation_unit_id, provider, model_name, prompt_version
                ) VALUES (?, ?, ?, ?, 'AI', ?, ?, ?, ?, ?, ?, ?)
                """, UUID.randomUUID().toString(), commit.bidId(), commit.chapterId(),
                (latest == null ? 0 : latest) + 1, commit.assembledChapterContent(),
                commit.assembledChapterHash(), commit.chapterSummary(), commit.unitId(),
                commit.provider(), commit.modelName(), commit.promptVersion());
    }

    private void updateTaskProgress(String taskId) {
        jdbcTemplate.update("""
                UPDATE bid_generation_task
                SET completed_units = LEAST(total_units, completed_units + 1),
                    heartbeat_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'RUNNING'
                """, taskId);
    }

    private void requireTaskRunning(String taskId) {
        Long running = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM bid_generation_task WHERE id = ? AND status = 'RUNNING'
                """, Long.class, taskId);
        if (running == null || running == 0) {
            throw new BusinessException(
                    "BID_GENERATION_PAUSED", "正文生成任务已暂停，本次模型调用不再执行", 409);
        }
    }

    private void markRunInterrupted(String aiRunId, String attemptId) {
        if (aiRunId == null || attemptId == null) {
            return;
        }
        jdbcTemplate.update("""
                UPDATE bid_ai_run SET status = 'FAILED', error_code = 'TASK_PAUSED',
                    error_message = '正文任务已暂停', failure_reason = 'TASK_NOT_RUNNING',
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND current_attempt_id = ? AND status = 'RUNNING'
                """, aiRunId, attemptId);
        interruptAttempt(attemptId, "TASK_PAUSED", "正文任务已暂停", "TASK_NOT_RUNNING");
    }

    private Optional<BidProductionRepository.AiRunHandle> findRun(String idempotencyKey) {
        return jdbcTemplate.query("""
                SELECT id, current_attempt_id, status, attempt_count
                FROM bid_ai_run WHERE idempotency_key = ?
                """, (rs, row) -> new BidProductionRepository.AiRunHandle(
                rs.getString("id"), rs.getString("current_attempt_id"),
                rs.getString("status"), rs.getInt("attempt_count")),
                idempotencyKey).stream().findFirst();
    }

    private void insertAttempt(String attemptId, String aiRunId, int attemptNo) {
        jdbcTemplate.update("""
                INSERT INTO bid_ai_run_attempt(id, ai_run_id, attempt_no, status)
                VALUES (?, ?, ?, 'RUNNING')
                """, attemptId, aiRunId, attemptNo);
    }

    private void completeAttempt(
            String attemptId, long durationMillis, Long inputTokens, Long outputTokens,
            Long reasoningTokens, Long cachedInputTokens, String finishReason,
            Integer responseLength, String responseHash, Integer modelAttempts) {
        if (attemptId == null) {
            return;
        }
        jdbcTemplate.update("""
                UPDATE bid_ai_run_attempt SET status = 'SUCCEEDED', duration_ms = ?,
                    input_tokens = ?, output_tokens = ?, reasoning_tokens = ?,
                    cached_input_tokens = ?, model_attempt_count = COALESCE(?, 1),
                    finish_reason = ?, response_length = ?, response_hash = ?,
                    finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'RUNNING'
                """, durationMillis, inputTokens, outputTokens, reasoningTokens,
                cachedInputTokens, modelAttempts, finishReason, responseLength,
                responseHash, attemptId);
    }

    private void failAttempt(
            String attemptId, long durationMillis, Long inputTokens, Long outputTokens,
            Long reasoningTokens, Long cachedInputTokens,
            String errorCode, String errorMessage,
            String failureReason, String finishReason, Integer responseLength,
            String responseHash, Integer modelAttempts) {
        if (attemptId == null) {
            return;
        }
        jdbcTemplate.update("""
                UPDATE bid_ai_run_attempt SET status = 'FAILED', duration_ms = ?,
                    input_tokens = ?, output_tokens = ?, reasoning_tokens = ?,
                    cached_input_tokens = ?, model_attempt_count = COALESCE(?, 1),
                    error_code = ?, error_message = ?,
                    failure_reason = ?, finish_reason = ?, response_length = ?, response_hash = ?,
                    finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'RUNNING'
                """, durationMillis, inputTokens, outputTokens, reasoningTokens,
                cachedInputTokens, modelAttempts, errorCode, limit(errorMessage),
                diagnostic(failureReason), finishReason, responseLength, responseHash, attemptId);
    }

    private void interruptAttempt(
            String attemptId, String errorCode, String message, String failureReason
    ) {
        if (attemptId == null) {
            return;
        }
        jdbcTemplate.update("""
                UPDATE bid_ai_run_attempt SET status = 'INTERRUPTED', error_code = ?,
                    error_message = ?, failure_reason = ?,
                    finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'RUNNING'
                """, errorCode, limit(message), failureReason, attemptId);
    }

    private void appendEvent(String taskId, String bidId, String chapterId, String type, String message) {
        jdbcTemplate.update("""
                INSERT INTO bid_generation_event(id, task_id, bid_id, chapter_id, event_type, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """, UUID.randomUUID().toString(), taskId, bidId, chapterId, type, limit(message));
    }

    private BidGenerationUnit unit(ResultSet rs) throws SQLException {
        return new BidGenerationUnit(
                rs.getString("id"), rs.getString("task_id"), rs.getString("bid_id"),
                rs.getString("chapter_id"), rs.getInt("unit_index"), rs.getString("unit_title"),
                rs.getString("idempotency_key"), rs.getString("status"), rs.getInt("attempt_count"),
                rs.getInt("word_budget"),
                BidJdbcMappers.nullableInteger(rs.getObject("visible_characters")),
                rs.getObject("budget_variance_ratio") == null
                        ? null : rs.getDouble("budget_variance_ratio"),
                rs.getString("budget_status"),
                BidJdbcMappers.nullableTime(rs, "compacted_at"),
                rs.getString("content"), rs.getString("content_hash"),
                rs.getString("summary"), rs.getString("previous_summary"),
                rs.getString("error_message"), JdbcTimes.localDateTime(rs, "updated_at"));
    }

    private String limit(String value) {
        String normalized = value == null || value.isBlank() ? "正文生成失败" : value;
        return normalized.substring(0, Math.min(1000, normalized.length()));
    }

    private String diagnostic(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.substring(0, Math.min(1000, value.length()));
    }
}
