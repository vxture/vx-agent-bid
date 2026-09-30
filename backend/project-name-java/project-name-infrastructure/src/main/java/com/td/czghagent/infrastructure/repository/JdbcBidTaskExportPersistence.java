// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-27
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.BidExport;
import com.td.czghagent.domain.model.BidWorkspace;
import com.td.czghagent.domain.model.PageCursor;
import com.td.czghagent.domain.repository.BidRepository;
import java.time.LocalDateTime;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.UUID;

final class JdbcBidTaskExportPersistence {
    private final JdbcTemplate jdbcTemplate;

    JdbcBidTaskExportPersistence(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    String createOutlineTask(String bidId) {
        long inputRevision = lockBid(bidId);
        List<String> active = jdbcTemplate.queryForList("""
                SELECT id FROM bid_outline_task
                WHERE bid_id = ? AND status IN ('PENDING', 'RUNNING')
                ORDER BY created_at DESC, id DESC LIMIT 1
                """, String.class, bidId);
        if (!active.isEmpty()) {
            return null;
        }
        String taskId = UUID.randomUUID().toString();
        jdbcTemplate.update("""
                INSERT INTO bid_outline_task(
                    id, bid_id, status, stage, progress, input_revision
                ) VALUES (?, ?, 'PENDING', 'QUEUED', 0, ?)
                """, taskId, bidId, inputRevision);
        jdbcTemplate.update("""
                UPDATE bid_document SET workflow_step = 'OUTLINE', status = 'OUTLINE_GENERATING',
                    error_message = NULL, updated_at = CURRENT_TIMESTAMP,
                    revision = revision + 1 WHERE id = ?
                """, bidId);
        return taskId;
    }

    void assignOutlineWorkflowRun(String taskId, String workflowRunId) {
        jdbcTemplate.update("""
                UPDATE bid_outline_task SET workflow_run_id = ? WHERE id = ?
                """, workflowRunId, taskId);
    }

    boolean updateOutlineTaskProgress(String taskId, String stage, int progress) {
        return jdbcTemplate.update("""
                UPDATE bid_outline_task SET status = 'RUNNING', stage = ?,
                    progress = GREATEST(progress, ?),
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
                WHERE id = ? AND status IN ('PENDING', 'RUNNING')
                """, stage, progress, taskId) == 1;
    }

    boolean completeOutlineTask(String taskId, List<String> warnings) {
        String warningsJson = warnings == null || warnings.isEmpty()
                ? null : BidJdbcMappers.writeJson(warnings);
        return jdbcTemplate.update("""
                UPDATE bid_outline_task SET status = 'SUCCEEDED', stage = 'COMPLETE',
                    progress = 100, error_message = NULL, warnings_json = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('PENDING', 'RUNNING')
                """, warningsJson, taskId) == 1;
    }

    boolean failOutlineTask(String taskId, String bidId, String errorMessage) {
        int updated = jdbcTemplate.update("""
                UPDATE bid_outline_task SET status = 'FAILED', stage = 'FAILED',
                    error_message = ?, finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('PENDING', 'RUNNING')
                """, errorMessage, taskId);
        if (updated == 1) {
            jdbcTemplate.update("""
                    UPDATE bid_document SET status = 'FAILED', error_message = ?,
                        updated_at = CURRENT_TIMESTAMP, revision = revision + 1
                    WHERE id = ? AND status = 'OUTLINE_GENERATING'
                    """, errorMessage, bidId);
        }
        return updated == 1;
    }

    String createGenerationTask(String bidId, int totalUnits) {
        lockBid(bidId);
        Long active = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM bid_generation_task
                WHERE bid_id = ? AND status IN ('PENDING', 'RUNNING')
                """, Long.class, bidId);
        if (active != null && active > 0) {
            throw new BusinessException(
                    "BID_GENERATION_RUNNING", "正文正在生成", 409);
        }
        String taskId = UUID.randomUUID().toString();
        jdbcTemplate.update("""
                INSERT INTO bid_generation_task(id, bid_id, status, total_units, completed_units)
                VALUES (?, ?, 'PENDING', ?, 0)
                """, taskId, bidId, totalUnits);
        jdbcTemplate.update("""
                UPDATE bid_document SET workflow_step = 'CONTENT', status = 'GENERATING',
                    content_status = 'GENERATING', error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP, revision = revision + 1 WHERE id = ?
                """, bidId);
        jdbcTemplate.update("""
                UPDATE bid_chapter SET generation_status = 'PENDING'
                WHERE bid_id = ? AND generation_status <> 'MANUAL'
                """, bidId);
        return taskId;
    }

    void startGenerationTask(String taskId) {
        int updated = jdbcTemplate.update("""
                UPDATE bid_generation_task SET status = 'RUNNING',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at = NULL, error_message = NULL
                WHERE id = ? AND status = 'PENDING'
                """, taskId);
        if (updated == 1) {
            jdbcTemplate.update("""
                UPDATE bid_document SET workflow_step = 'CONTENT', status = 'GENERATING',
                    content_status = 'GENERATING', error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT bid_id FROM bid_generation_task WHERE id = ?)
                """, taskId);
        }
    }

    boolean saveGeneratedChapter(String chapterId, String content) {
        return jdbcTemplate.update("""
                UPDATE bid_chapter SET content = ?, generation_status = 'READY',
                    updated_at = CURRENT_TIMESTAMP, revision = revision + 1
                WHERE id = ? AND generation_status <> 'MANUAL'
                """, content, chapterId) == 1;
    }

    void advanceGenerationTask(String taskId) {
        jdbcTemplate.update("""
                UPDATE bid_generation_task SET completed_units = completed_units + 1 WHERE id = ?
                """, taskId);
    }

    boolean completeGenerationTask(String taskId, String bidId) {
        int updated = jdbcTemplate.update("""
                UPDATE bid_generation_task SET status = 'SUCCEEDED', completed_units = total_units,
                    finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'RUNNING'
                """, taskId);
        if (updated == 1) {
            jdbcTemplate.update("""
                    UPDATE bid_document SET content_stale = FALSE, stale_reason = NULL,
                        error_message = NULL, updated_at = CURRENT_TIMESTAMP,
                        revision = revision + 1 WHERE id = ?
                    """, bidId);
        }
        return updated == 1;
    }

    boolean failGenerationTask(String taskId, String bidId, String message) {
        int updated = jdbcTemplate.update("""
                UPDATE bid_generation_task SET status = 'FAILED', error_message = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('PENDING', 'RUNNING')
                """, message, taskId);
        if (updated == 1) {
            jdbcTemplate.update("""
                    UPDATE bid_document SET status = 'FAILED', content_status = 'REVIEW',
                        error_message = ?, updated_at = CURRENT_TIMESTAMP,
                        revision = revision + 1 WHERE id = ?
                    """, message, bidId);
        }
        return updated == 1;
    }

    /**
     * 原子暂停最新正文任务。
     *
     * <p><b>Preconditions:</b> 标书已由调用层完成所有权校验。</p>
     * <p><b>Side Effects:</b> 保留成功单元，将在途单元和章节恢复为待处理，并关闭运行中AI审计。</p>
     * <p><b>Error Semantics:</b> 重复暂停幂等；终态任务返回业务冲突。</p>
     */
    BidRepository.GenerationTaskExecution pauseGenerationTask(String bidId) {
        lockBid(bidId);
        BidRepository.GenerationTaskExecution current = requireLatestGenerationTask(bidId);
        if ("PAUSED".equals(current.status())) {
            return withChanged(current, false);
        }
        if (!List.of("PENDING", "RUNNING").contains(current.status())) {
            throw new BusinessException("BID_GENERATION_NOT_ACTIVE", "当前没有可停止的正文任务", 409);
        }
        jdbcTemplate.update("""
                UPDATE bid_generation_task SET status = 'PAUSED', error_message = NULL,
                    completed_units = (SELECT COUNT(*) FROM bid_generation_unit
                        WHERE task_id = ? AND status IN ('SUCCEEDED', 'SKIPPED')),
                    heartbeat_at = CURRENT_TIMESTAMP, finished_at = NULL WHERE id = ?
                """, current.taskId(), current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_generation_unit SET status = 'PENDING', error_message = NULL,
                    finished_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND status = 'RUNNING'
                """, current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_ai_run_attempt SET status = 'INTERRUPTED',
                    error_code = 'TASK_PAUSED', error_message = '正文任务已暂停',
                    failure_reason = 'USER_PAUSED', finished_at = CURRENT_TIMESTAMP
                WHERE status = 'RUNNING' AND id IN (
                    SELECT current_attempt_id FROM bid_ai_run
                    WHERE task_id = ? AND status = 'RUNNING'
                )
                """, current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_ai_run SET status = 'FAILED', error_code = 'TASK_PAUSED',
                    error_message = '正文任务已暂停', failure_reason = 'USER_PAUSED',
                    finished_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND status = 'RUNNING'
                """, current.taskId());
        resetChapterGenerationStates(current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_document SET status = 'GENERATION_PAUSED', error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP, revision = revision + 1 WHERE id = ?
                """, bidId);
        appendGenerationEvent(current.taskId(), bidId, "TASK_PAUSED",
                "正文生成已停止，已完成内容均已保留");
        return new BidRepository.GenerationTaskExecution(
                current.taskId(), bidId, "PAUSED", current.snapshotId(), current.snapshotHash(),
                current.workflowRunId(), current.retryCount(), true);
    }

    /**
     * 原子准备同一任务的下一次工作流执行。
     *
     * <p><b>Preconditions:</b> 最新任务已暂停或失败，且持有不可变快照。</p>
     * <p><b>Side Effects:</b> 只重置未成功单元，重新计算进度并递增任务级重试次数。</p>
     * <p><b>Error Semantics:</b> 已经等待或运行时幂等返回；不可恢复任务返回业务冲突。</p>
     */
    BidRepository.GenerationTaskExecution resumeGenerationTask(String bidId) {
        lockBid(bidId);
        BidRepository.GenerationTaskExecution current = requireLatestGenerationTask(bidId);
        if (List.of("PENDING", "RUNNING").contains(current.status())) {
            return withChanged(current, false);
        }
        if (!List.of("PAUSED", "FAILED").contains(current.status())) {
            throw new BusinessException("BID_GENERATION_NOT_RESUMABLE", "当前正文任务不能继续", 409);
        }
        if (current.snapshotId() == null || current.snapshotHash() == null) {
            throw new BusinessException(
                    "BID_GENERATION_NOT_RESUMABLE", "当前正文任务缺少生成快照，不能断点继续", 409);
        }
        jdbcTemplate.update("""
                UPDATE bid_generation_unit SET status = 'PENDING', error_message = NULL,
                    started_at = NULL, finished_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND status NOT IN ('SUCCEEDED', 'SKIPPED')
                """, current.taskId());
        resetChapterGenerationStates(current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_generation_task SET status = 'PENDING',
                    completed_units = (SELECT COUNT(*) FROM bid_generation_unit
                        WHERE task_id = ? AND status IN ('SUCCEEDED', 'SKIPPED')),
                    error_message = NULL, workflow_run_id = NULL,
                    retry_count = retry_count + 1, heartbeat_at = CURRENT_TIMESTAMP,
                    finished_at = NULL WHERE id = ?
                """, current.taskId(), current.taskId());
        jdbcTemplate.update("""
                UPDATE bid_document SET workflow_step = 'CONTENT', status = 'GENERATING',
                    content_status = 'GENERATING', error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP, revision = revision + 1 WHERE id = ?
                """, bidId);
        appendGenerationEvent(current.taskId(), bidId, "TASK_RESUMED",
                "继续生成未完成内容，已完成部分不会重复编写");
        return new BidRepository.GenerationTaskExecution(
                current.taskId(), bidId, "PENDING", current.snapshotId(), current.snapshotHash(),
                null, current.retryCount() + 1, true);
    }

    int nextExportVersion(String bidId) {
        Integer version = jdbcTemplate.queryForObject(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM bid_export WHERE bid_id = ?",
                Integer.class, bidId);
        return version == null ? 1 : version;
    }

    void insertExport(BidRepository.ExportRecord export) {
        jdbcTemplate.update("""
                INSERT INTO bid_export(
                    id, bid_id, version_no, file_name, object_key, file_size, created_by,
                    layout_job_id, qa_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, export.id(), export.bidId(), export.version(), export.fileName(),
                export.objectKey(), export.fileSize(), export.createdBy(),
                export.layoutJobId(), export.qaStatus());
        jdbcTemplate.update("""
                UPDATE bid_document SET status = 'EXPORTED', updated_at = CURRENT_TIMESTAMP,
                    revision = revision + 1 WHERE id = ?
                """, export.bidId());
    }

    /**
     * 先 {@code FOR UPDATE} 锁行，再判、再写。
     *
     * <p>不锁的话，两次并发导出会都读到旧水位：前一个抬到 100 报 100，后一个抬到 150
     * 却按旧水位 0 报 150——重叠的 100 字被记了两遍，而两笔的幂等键不同，谁也拦不住。
     * 锁住之后，后到的那个等前一个提交，读到的是 100，只报 50。
     */
    OptionalLong raiseMeteredCharacters(String bidId, long characters) {
        Long previous = jdbcTemplate.queryForObject(
                "SELECT metered_characters FROM bid_document WHERE id = ? FOR UPDATE",
                Long.class, bidId);
        if (previous == null || previous >= characters) {
            return OptionalLong.empty();
        }
        jdbcTemplate.update(
                "UPDATE bid_document SET metered_characters = ? WHERE id = ?", characters, bidId);
        return OptionalLong.of(previous);
    }

    /**
     * 工作台与元数据里内嵌的导出列表只带最近这么多份——写下来的上限（通则 A-3）。
     * 完整历史走游标分页的 {@code GET /api/bids/{bidId}/exports}。
     */
    static final int WORKSPACE_EXPORT_LIMIT = 20;

    /** 键集分页，{@code (created_at, id)} 降序；第一条就是最近生成的那份。 */
    List<BidExport> listExports(String bidId, PageCursor after, int limit) {
        if (after == null) {
            return jdbcTemplate.query("""
                    SELECT * FROM bid_export WHERE bid_id = ?
                    ORDER BY created_at DESC, id DESC LIMIT ?
                    """, BidJdbcMappers.EXPORT, bidId, limit);
        }
        return jdbcTemplate.query("""
                SELECT * FROM bid_export WHERE bid_id = ?
                  AND (created_at < ? OR (created_at = ? AND id < ?))
                ORDER BY created_at DESC, id DESC LIMIT ?
                """, BidJdbcMappers.EXPORT,
                bidId, after.createdAt(), after.createdAt(), after.id(), limit);
    }

    List<BidExport> recentExports(String bidId) {
        return listExports(bidId, null, WORKSPACE_EXPORT_LIMIT);
    }

    Optional<BidExport> findExportSummary(String bidId, String exportId) {
        return jdbcTemplate.query("""
                SELECT * FROM bid_export WHERE bid_id = ? AND id = ?
                """, BidJdbcMappers.EXPORT, bidId, exportId).stream().findFirst();
    }

    Optional<BidRepository.ExportRecord> findExport(String bidId, String exportId) {
        return jdbcTemplate.query("""
                SELECT * FROM bid_export WHERE bid_id = ? AND id = ?
                """, (rs, row) -> new BidRepository.ExportRecord(
                rs.getString("id"), rs.getString("bid_id"), rs.getInt("version_no"),
                rs.getString("file_name"), rs.getString("object_key"), rs.getLong("file_size"),
                rs.getString("created_by"), rs.getString("layout_job_id"), rs.getString("qa_status")),
                bidId, exportId).stream().findFirst();
    }

    Optional<BidRepository.ExportRecord> findLatestExport(String bidId) {
        return jdbcTemplate.query("""
                SELECT * FROM bid_export WHERE bid_id = ? ORDER BY version_no DESC LIMIT 1
                """, (rs, row) -> new BidRepository.ExportRecord(
                rs.getString("id"), rs.getString("bid_id"), rs.getInt("version_no"),
                rs.getString("file_name"), rs.getString("object_key"), rs.getLong("file_size"),
                rs.getString("created_by"), rs.getString("layout_job_id"), rs.getString("qa_status")),
                bidId).stream().findFirst();
    }

    BidWorkspace.GenerationTask latestTask(String bidId) {
        return jdbcTemplate.query("""
                SELECT * FROM bid_generation_task WHERE bid_id = ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """, (rs, row) -> new BidWorkspace.GenerationTask(
                rs.getString("id"), rs.getString("status"), rs.getInt("total_units"),
                rs.getInt("completed_units"), rs.getString("error_message"),
                JdbcTimes.localDateTime(rs, "created_at"),
                BidJdbcMappers.nullableTime(rs, "finished_at")), bidId)
                .stream().findFirst().orElse(null);
    }

    BidWorkspace.OutlineTask latestOutlineTask(String bidId) {
        return jdbcTemplate.query("""
                SELECT * FROM bid_outline_task WHERE bid_id = ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """, (rs, row) -> new BidWorkspace.OutlineTask(
                rs.getString("id"), rs.getString("status"), rs.getString("stage"),
                rs.getInt("progress"), rs.getLong("input_revision"),
                rs.getString("workflow_run_id"),
                rs.getString("error_message"), JdbcTimes.localDateTime(rs, "created_at"),
                BidJdbcMappers.nullableTime(rs, "started_at"),
                BidJdbcMappers.nullableTime(rs, "finished_at"),
                BidJdbcMappers.parseStringList(rs.getString("warnings_json"))), bidId)
                .stream().findFirst().orElse(null);
    }

    private long lockBid(String bidId) {
        Long revision = jdbcTemplate.queryForObject(
                "SELECT revision FROM bid_document WHERE id = ? FOR UPDATE", Long.class, bidId);
        if (revision == null) {
            throw new IllegalStateException("标书不存在");
        }
        return revision;
    }

    private BidRepository.GenerationTaskExecution requireLatestGenerationTask(String bidId) {
        return jdbcTemplate.query("""
                SELECT id, bid_id, status, snapshot_id, snapshot_hash,
                       workflow_run_id, retry_count
                FROM bid_generation_task WHERE bid_id = ?
                ORDER BY created_at DESC, id DESC LIMIT 1 FOR UPDATE
                """, (rs, row) -> new BidRepository.GenerationTaskExecution(
                rs.getString("id"), rs.getString("bid_id"), rs.getString("status"),
                rs.getString("snapshot_id"), rs.getString("snapshot_hash"),
                rs.getString("workflow_run_id"), rs.getInt("retry_count"), false), bidId)
                .stream().findFirst().orElseThrow(() -> new BusinessException(
                        "BID_GENERATION_NOT_FOUND", "正文生成任务不存在", 409));
    }

    private BidRepository.GenerationTaskExecution withChanged(
            BidRepository.GenerationTaskExecution task, boolean changed) {
        return new BidRepository.GenerationTaskExecution(
                task.taskId(), task.bidId(), task.status(), task.snapshotId(), task.snapshotHash(),
                task.workflowRunId(), task.retryCount(), changed);
    }

    private void resetChapterGenerationStates(String taskId) {
        jdbcTemplate.update("""
                UPDATE bid_chapter c SET generation_status = CASE
                    WHEN c.generation_status = 'MANUAL' THEN 'MANUAL'
                    WHEN EXISTS(SELECT 1 FROM bid_generation_unit u
                        WHERE u.task_id = ? AND u.chapter_id = c.id
                          AND u.status NOT IN ('SUCCEEDED', 'SKIPPED')) THEN 'PENDING'
                    ELSE 'READY' END
                WHERE c.id IN (SELECT chapter_id FROM bid_generation_unit WHERE task_id = ?)
                """, taskId, taskId);
    }

    private void appendGenerationEvent(String taskId, String bidId, String type, String message) {
        jdbcTemplate.update("""
                INSERT INTO bid_generation_event(id, task_id, bid_id, event_type, message)
                VALUES (?, ?, ?, ?, ?)
                """, UUID.randomUUID().toString(), taskId, bidId, type, message);
    }
}
