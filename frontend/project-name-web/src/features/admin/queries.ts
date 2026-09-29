// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { useMutation, useQuery } from '@tanstack/react-query'

import { adminApi } from '@/api/modules/admin'
import type { AuditLogFilters } from '@/types/admin'

const adminKeys = {
  auditLogs: (filters: AuditLogFilters) => ['admin-audit-logs', filters] as const,
  platformCheck: ['admin-platform-check'] as const,
}

export const useAuditLogsQuery = (filters: AuditLogFilters) =>
  useQuery({
    queryKey: adminKeys.auditLogs(filters),
    queryFn: () => adminApi.listAuditLogs(filters),
  })

/**
 * 系统验证的只读探测。
 *
 * 不缓存、不在窗口聚焦时重打：每一次都会真的去换票、读权益、读 Atlas 模型清单，
 * 结论应当由管理员点「重新探测」时产生，而不是切个标签页就悄悄换掉。
 */
export const usePlatformCheckQuery = () =>
  useQuery({
    queryKey: adminKeys.platformCheck,
    queryFn: () => adminApi.platformCheck(),
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  })

/** 会花钱的两项探测：只在确认后触发，从不重试。 */
export const useAtlasProbeMutation = () =>
  useMutation({ mutationFn: () => adminApi.probeAtlas(), retry: false })

export const useUsageReplayProbeMutation = () =>
  useMutation({ mutationFn: () => adminApi.probeUsageReplay(), retry: false })
