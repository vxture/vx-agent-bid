// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { apiRequest } from '@/api/client'
import type {
  AuditLogEntry,
  AuditLogFilters,
  CursorPage,
  PlatformCheck,
  PlatformSpendResult,
} from '@/types/admin'

const query = (values: Record<string, string | number | null>) => {
  const result = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && String(value).trim()) result.set(key, String(value))
  })
  return result.toString()
}

/**
 * 管理面：审计流水与系统验证。本地账号管理（/api/admin/users*）2026-09-15 随本地账号体系
 * 退役：账号与身份归平台 IdP，那组接口管理的是再也登录不了的账号。
 */
export const adminApi = {
  /** 无界流水，返回 {items, nextCursor}（通则 A-3）。 */
  listAuditLogs: (filters: AuditLogFilters) =>
    apiRequest<CursorPage<AuditLogEntry>>(`/api/admin/audit-logs?${query({
      limit: filters.limit,
      cursor: filters.cursor,
      keyword: filters.keyword,
      actionCode: filters.actionCode,
      resultCode: filters.resultCode,
      startAt: filters.startDate ? `${filters.startDate}T00:00:00` : '',
      endAt: filters.endDate ? `${filters.endDate}T23:59:59` : '',
    })}`),
  /** 只读探测，每次都真打一遍，不产生费用。 */
  platformCheck: () => apiRequest<PlatformCheck>('/api/admin/platform-check'),
  /** 逐条路由各打一次 Atlas。会花钱，由 Atlas 自行计量。 */
  probeAtlas: () =>
    apiRequest<PlatformSpendResult>('/api/admin/platform-check/atlas-probe', { method: 'POST' }),
  /** C3 幂等重放。会花钱：每个工作空间每天至多一笔。 */
  probeUsageReplay: () =>
    apiRequest<PlatformSpendResult>('/api/admin/platform-check/usage-replay-probe', {
      method: 'POST',
    }),
}
