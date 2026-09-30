-- 列级 UPDATE 白名单（治理规范 §7）。先 REVOKE 整表 UPDATE，再按列 GRANT。
--
-- 白名单不是猜出来的：它由 scripts/guardrails/check_column_locks.py 从 19 个
-- JdbcTemplate 类里真实的 UPDATE 语句抽出来对账，CI 里守着。**新增一个可写列
-- 而不更新这里，服务写会 permission denied**——那是有意的：让「我加了一列」
-- 这件事必须同时说明「谁能写它」。
--
-- 锚点列（id / *_id 引用键 / created_at）永不可写。没有任何 UPDATE 的表
-- 是追加型账本，一律不给 UPDATE。
--
-- 一个提取上的坑记在这里：JdbcProvisioningRepository 用 %s 拼动态列名
-- （provisioned_at / deprovisioned_at 二选一），机械抽取会得到一列叫 `s`。
-- 白名单必须人工复核，不能直接用抽取结果。


-- --- vx_provision ---
REVOKE UPDATE ON vx_provision.platform_provision_delivery FROM tenderforge_svc;
GRANT UPDATE (outcome)
  ON vx_provision.platform_provision_delivery TO tenderforge_svc;
REVOKE UPDATE ON vx_provision.platform_workspace_provision FROM tenderforge_svc;
GRANT UPDATE (deprovisioned_at, last_seq, provisioned_at, state, updated_at)
  ON vx_provision.platform_workspace_provision TO tenderforge_svc;

-- --- local_authz ---
REVOKE UPDATE ON local_authz.app_user FROM tenderforge_svc;
-- app_user: 本地账号管理与资料编辑 2026-09-15 退役，代码里没有任何 UPDATE —— 不给 UPDATE。
REVOKE UPDATE ON local_authz.oidc_authorization_request FROM tenderforge_svc;
-- oidc_authorization_request: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON local_authz.rp_session FROM tenderforge_svc;
GRANT UPDATE (access_expires_at, access_token, last_seen_at, refresh_token)
  ON local_authz.rp_session TO tenderforge_svc;
REVOKE UPDATE ON local_authz.user_session FROM tenderforge_svc;
-- user_session: 本地口令会话 2026-09-15 退役，代码里没有任何 UPDATE —— 不给 UPDATE。

-- --- local_usage ---
REVOKE UPDATE ON local_usage.platform_usage_event FROM tenderforge_svc;
GRANT UPDATE (attempts, claim_token, claimed_at, flushed_at, last_error, platform_event_id)
  ON local_usage.platform_usage_event TO tenderforge_svc;
-- platform_event_id 由 incr/0002 加上：本文件排在增量之后施加，活库上这条 GRANT 才找得到列。

-- --- bid ---
REVOKE UPDATE ON bid.audit_log FROM tenderforge_svc;
-- audit_log: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_document FROM tenderforge_svc;
GRANT UPDATE (bidding_mode, content_hash, content_stale, content_status, content_version, error_message, interpretation_hash, interpretation_status, interpretation_version, metered_characters, outline_hash, outline_status, outline_version, revision, stale_reason, status, target_pages, title, updated_at, workflow_step)
  ON bid.bid_document TO tenderforge_svc;
-- metered_characters 由 incr/0001 加上：本文件排在增量之后施加，活库上这条 GRANT 才找得到列。
REVOKE UPDATE ON bid.bid_generation_task FROM tenderforge_svc;
-- retry_count 一度漏在这里：那条 UPDATE 的 SET 子句里有个带自己 WHERE 的
-- 子查询（completed_units = (SELECT ... WHERE ...)），静态提取停在了那个
-- WHERE 上，后面的列全丢了。提取器已改成按括号深度切。
GRANT UPDATE (completed_units, error_message, finished_at, heartbeat_at,
              retry_count, snapshot_hash, snapshot_id, started_at, status, workflow_run_id)
  ON bid.bid_generation_task TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_generation_snapshot FROM tenderforge_svc;
-- bid_generation_snapshot: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_ai_run FROM tenderforge_svc;
GRANT UPDATE (attempt_count, cached_input_tokens, current_attempt_id, duration_ms, error_code, error_message, failure_reason, finish_reason, finished_at, input_tokens, model_attempt_count, object_name, output_hash, output_tokens, reasoning_tokens, response_fields, response_hash, response_length, schema_version, status)
  ON bid.bid_ai_run TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_ai_run_attempt FROM tenderforge_svc;
GRANT UPDATE (cached_input_tokens, duration_ms, error_code, error_message, failure_reason, finish_reason, finished_at, input_tokens, model_attempt_count, output_tokens, reasoning_tokens, response_hash, response_length, status)
  ON bid.bid_ai_run_attempt TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_reference_asset FROM tenderforge_svc;
GRANT UPDATE (ingestion_error, revision, status, updated_at)
  ON bid.bid_reference_asset TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_asset_chunk FROM tenderforge_svc;
-- bid_asset_chunk: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_asset_selection FROM tenderforge_svc;
-- bid_asset_selection: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_outline_node FROM tenderforge_svc;
GRANT UPDATE (must_keywords_json, planned_pages, revision, scoring_point_ids_json, sort_order, task_brief, title)
  ON bid.bid_outline_node TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_chapter FROM tenderforge_svc;
GRANT UPDATE (content, generation_status, revision, title, updated_at)
  ON bid.bid_chapter TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_generation_unit FROM tenderforge_svc;
GRANT UPDATE (ai_run_id, attempt_count, budget_status, budget_variance_ratio, compacted_at, content, content_hash, error_message, finished_at, started_at, status, summary, updated_at, visible_characters)
  ON bid.bid_generation_unit TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_chapter_version FROM tenderforge_svc;
-- bid_chapter_version: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_layout_job FROM tenderforge_svc;
GRANT UPDATE (actual_pages, error_message, finished_at, qa_status, qa_summary, status, workflow_run_id)
  ON bid.bid_layout_job TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_export FROM tenderforge_svc;
-- bid_export: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_interpretation_version FROM tenderforge_svc;
-- bid_interpretation_version: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_frozen_fact FROM tenderforge_svc;
-- bid_frozen_fact: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_generation_event FROM tenderforge_svc;
-- bid_generation_event: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_outline_regeneration_archive FROM tenderforge_svc;
-- bid_outline_regeneration_archive: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_outline_task FROM tenderforge_svc;
GRANT UPDATE (error_message, finished_at, progress, stage, started_at, status, warnings_json,
  workflow_run_id)
  ON bid.bid_outline_task TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_outline_stage_result FROM tenderforge_svc;
GRANT UPDATE (attempt_count, duration_ms, error_code, error_message, finished_at, input_hash, model_name, output_hash, output_payload, started_at, status)
  ON bid.bid_outline_stage_result TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_requirement_conflict FROM tenderforge_svc;
-- bid_requirement_conflict: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_requirement_item FROM tenderforge_svc;
-- bid_requirement_item: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_review_issue FROM tenderforge_svc;
-- bid_review_issue: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_scoring_criterion FROM tenderforge_svc;
-- bid_scoring_criterion: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_snapshot_asset_chunk FROM tenderforge_svc;
-- bid_snapshot_asset_chunk: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_snapshot_branch_blueprint FROM tenderforge_svc;
-- bid_snapshot_branch_blueprint: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_snapshot_fact FROM tenderforge_svc;
-- bid_snapshot_fact: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_snapshot_outline FROM tenderforge_svc;
GRANT UPDATE (chapter_id)
  ON bid.bid_snapshot_outline TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_snapshot_requirement FROM tenderforge_svc;
-- bid_snapshot_requirement: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
REVOKE UPDATE ON bid.bid_source_file FROM tenderforge_svc;
-- overview_* 与 scoring_* 这两套列是 JdbcBidDraftPersistence.objectColumn()
-- 按解读对象类型**运行时拼**出来的，源码里不存在 `overview_content = ?`
-- 这样的字面量——静态提取看不见它们，是以受限角色跑的集成测试报
-- permission denied 才发现的。
GRANT UPDATE (error_message, extracted_text, parse_finished_at, parse_progress,
              parse_stage, parse_started_at, parse_status, updated_at,
              overview_status, overview_content, overview_error_message, overview_completed_at,
              scoring_status, scoring_content, scoring_error_message, scoring_completed_at)
  ON bid.bid_source_file TO tenderforge_svc;
REVOKE UPDATE ON bid.bid_source_segment FROM tenderforge_svc;
-- bid_source_segment: 代码里没有任何 UPDATE —— 追加型，不给 UPDATE。
