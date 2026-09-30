-- 0005 · bid_outline_task.warnings_json：目录生成的提示（2026-09-30）
--
-- 目录规模与篇幅估算的偏差（二级过多/过少、三级总数偏离 ±20%、略去的空章节）从此只提示、
-- 不让整份目录失败（owner 2026-09-30：「生成了就应该展示，而且应该是警示性提示」）。
-- 提示由 AI 服务在装配目录时给出，此前 Java 收到后就丢了——页面无从显示。
-- 随目录任务保存，页面刷新后仍在；新一次生成覆盖旧任务，提示随之更新。
--
-- JSON 字符串数组。可空：本增量之前完成的任务、以及没有任何提示的任务都为空。
-- 完成目录任务时 UPDATE，所以 98 的白名单同批加上这一列。
-- 只加在增量里、不改基线（见本目录 README）。
ALTER TABLE bid.bid_outline_task
  ADD COLUMN IF NOT EXISTS warnings_json TEXT;

COMMENT ON COLUMN bid.bid_outline_task.warnings_json IS
  '目录生成提示（JSON 字符串数组）：规模偏差、略去的空章节；只提示，不代表失败';
