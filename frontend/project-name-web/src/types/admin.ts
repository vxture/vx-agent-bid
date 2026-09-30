// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
/** 游标分页形状移到 types/page，标书、素材、导出列表与审计共用同一个定义。 */
export type { CursorPage } from './page'

/**
 * 审计条目，字段名取自《产品接入通则》X-3 的最小字段集。
 *
 * 这些名字不是本仓的偏好，是跨产品对账的前提——三个产品各写各的名字，
 * 「都合规」与「能一起查」就不是一回事了。
 *
 * `actorName` / `objectName` 是服务端 join 出来的展示字段，不属于最小集，
 * 不要拿它们做任何判断：被引用对象一改名它们就变了。
 */
export interface AuditLogEntry {
  eventId: string
  actorId: string | null
  actorName: string | null
  /** 发起动作的控制台 RP；后台通道为 null，不要在这里兜底成产品名。 */
  actorConsole: string | null
  objectName: string | null
  action: string
  objectType: string
  objectId: string | null
  outcome: string
  detailSummary: string | null
  /** 跨产品聚合键（X-2）。调用方没送时为 null。 */
  taskId: string | null
  orgId: string | null
  workspaceId: string | null
  traceId: string
  ipAddress: string | null
  occurredAt: string
}

export interface AuditLogFilters {
  limit: number
  /** 服务端铸的不透明游标；null 表示第一页。不要自己构造它。 */
  cursor: string | null
  keyword: string
  actionCode: string
  resultCode: string
  startDate: string
  endDate: string
}

/**
 * 系统验证的一项探测（`GET /api/admin/platform-check`）。
 *
 * `configured=false` 时 `ok` 恒假：界面显示「未配置」而不是「异常」——
 * 没接的通道和接坏了的通道是两件事，混成一种红色会让人朝错误的方向查。
 */
export interface PlatformProbe {
  configured: boolean
  ok: boolean
  detail: string
}

export interface PlatformCheck {
  time: string
  c1: PlatformProbe
  tokenMint: PlatformProbe
  c2: PlatformProbe
  c3Up: PlatformProbe
  c3Down: PlatformProbe
  atlas: PlatformProbe
  /** 本产品实际路由的容量与推理模式核对（`GET /v1/model-routes`）。 */
  atlasRoutes: PlatformProbe
  usageReplay: PlatformProbe
}

/** 会花钱的探测的结果：整体结论 + 逐项明细。 */
export interface PlatformSpendResult {
  ok: boolean
  detail: string
  items: PlatformProbe[]
}
