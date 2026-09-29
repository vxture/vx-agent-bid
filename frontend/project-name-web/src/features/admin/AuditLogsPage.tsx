// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-27
import { type FormEvent, useState } from 'react'

import {
  Button,
  DataTable,
  type DataTableColumn,
  EmptyState,
  FilterBar,
  Icon,
  Input,
  ListPageTemplate,
  NativeSelect,
  ViewHeader,
} from '@vxture/design-system'

import { QueryError } from '@/components/QueryState'
import type { AuditLogEntry, AuditLogFilters } from '@/types/admin'

import { StatusBadge } from './components/StatusBadge'
import { formatDateTime } from './formatters'
import { useAuditLogsQuery } from './queries'

const DEFAULT_FILTERS: AuditLogFilters = {
  limit: 20,
  cursor: null,
  keyword: '',
  actionCode: '',
  resultCode: '',
  startDate: '',
  endDate: '',
}

const actionLabels: Record<string, string> = {
  AUTH_LOGIN: '登录',
  AUTH_LOGOUT: '退出登录',
  BID_CREATE: '新建标书',
  BID_SETUP_UPDATE: '更新标书设置',
  BID_SOURCE_UPLOAD: '上传招标文件',
  BID_SOURCE_PARSE_SUBMIT: '提交文件解读',
  BID_SOURCE_PARSE: '解读招标文件',
  BID_CRITERIA_UPDATE: '修订解读结果',
  BID_INTERPRETATION_FREEZE: '确认解读结果',
  BID_OUTLINE_GENERATE_SUBMIT: '提交目录生成',
  BID_OUTLINE_GENERATE: '生成目录',
  BID_OUTLINE_UPDATE: '更新目录',
  BID_OUTLINE_FREEZE: '确认目录',
  BID_CONTENT_GENERATE: '生成正文',
  BID_CONTENT_PAUSE: '停止正文生成',
  BID_CONTENT_RESUME: '继续正文生成',
  BID_CONTENT_REVIEW: '复审正文',
  BID_CHAPTER_UPDATE: '保存正文',
  BID_SECTION_AI_CANDIDATE: 'AI 修订正文',
  BID_CONTENT_FREEZE: '确认正文',
  BID_LAYOUT_START: '开始排版',
  BID_LAYOUT_COMPLETE: '完成排版',
  BID_EXPORT_CREATE: '导出标书',
  ACCOUNT_PROFILE_UPDATE: '更新个人资料',
  PLATFORM_PROBE_ATLAS: '运行 Atlas 探测',
  PLATFORM_PROBE_USAGE_REPLAY: '运行用量重放校验',
  ACCOUNT_AVATAR_UPDATE: '更新头像',
  ACCOUNT_PASSWORD_CHANGE: '修改密码',
  USER_CREATE: '新建用户',
  USER_UPDATE: '编辑用户',
  USER_ENABLE: '启用用户',
  USER_DISABLE: '停用用户',
}

const resultLabels: Record<string, string> = {
  SUCCESS: '成功',
  FAILED: '失败',
  DENIED: '拒绝',
}

const csvCell = (value: string | null) => {
  const safeValue = value && /^[=+\-@]/.test(value) ? `'${value}` : (value ?? '')
  return `"${safeValue.replaceAll('"', '""')}"`
}

/**
 * 导出当前筛选结果页。
 * @preconditions - logs 为当前服务端分页返回的审计记录
 * @sideEffects - 在浏览器触发 UTF-8 CSV 下载
 * @errorHandling - 转义公式前缀与双引号，避免表格软件执行日志内容
 */
const downloadAuditLogs = (logs: AuditLogEntry[]) => {
  const rows = [
    ['时间', '账号', '对象', '操作', '结果', '说明', '追踪号', 'IP'],
    ...logs.map((log) => [
      log.occurredAt,
      log.actorName ?? '',
      log.objectName ?? '',
      actionLabels[log.action] ?? log.action,
      resultLabels[log.outcome] ?? log.outcome,
      log.detailSummary ?? '',
      log.traceId,
      log.ipAddress ?? '',
    ]),
  ]
  const content = rows.map((row) => row.map(csvCell).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['\ufeff', content], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `TenderAgent-审计日志-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

const columns: DataTableColumn<AuditLogEntry>[] = [
  {
    id: 'occurredAt',
    header: '时间',
    width: 'md',
    cell: (log) => (
      <span className="whitespace-nowrap text-muted-foreground">
        {formatDateTime(log.occurredAt)}
      </span>
    ),
  },
  {
    id: 'actorName',
    header: '账号',
    width: 'sm',
    cell: (log) => log.actorName ?? '系统',
  },
  {
    id: 'objectName',
    header: '对象',
    width: 'md',
    cell: (log) => <span className="block max-w-sidebar-collapsed truncate">{log.objectName ?? '-'}</span>,
  },
  {
    id: 'action',
    header: '操作',
    width: 'sm',
    cell: (log) => actionLabels[log.action] ?? log.action,
  },
  {
    id: 'outcome',
    header: '结果',
    align: 'center',
    width: 'xs',
    cell: (log) => {
      const resultLabel = resultLabels[log.outcome] ?? log.outcome
      return <StatusBadge label={resultLabel} status={resultLabel} />
    },
  },
  {
    id: 'detailSummary',
    header: '说明',
    cell: (log) => (
      <span className="block max-w-sidebar-expanded truncate text-muted-foreground">
        {log.detailSummary ?? '-'}
      </span>
    ),
  },
  {
    id: 'traceId',
    header: '追踪号',
    width: 'md',
    cell: (log) => (
      <span className="block max-w-sidebar-collapsed truncate font-mono text-muted-foreground">
        {log.traceId}
      </span>
    ),
  },
]

export default function AuditLogsPage() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [draft, setDraft] = useState(DEFAULT_FILTERS)
  /**
   * 已经走过的游标，用来实现「上一页」。
   *
   * 键集游标只能往前走——服务端给的是「从这里继续」，不是「第 N 页」。
   * 回退能力因此必须由调用方自己记住来路；这个栈就是那份记忆。
   * 换筛选条件时清空：旧游标锚在旧结果集上，带着它翻会得到一段无法解释的结果。
   */
  const [visited, setVisited] = useState<(string | null)[]>([])
  const auditLogsQuery = useAuditLogsQuery(filters)

  const submitFilters = (event: FormEvent) => {
    event.preventDefault()
    setVisited([])
    setFilters({ ...draft, cursor: null })
  }

  const resetFilters = () => {
    setDraft(DEFAULT_FILTERS)
    setVisited([])
    setFilters(DEFAULT_FILTERS)
  }

  const goNext = (nextCursor: string) => {
    setVisited([...visited, filters.cursor])
    setFilters({ ...filters, cursor: nextCursor })
  }

  const goPrevious = () => {
    const previous = visited[visited.length - 1] ?? null
    setVisited(visited.slice(0, -1))
    setFilters({ ...filters, cursor: previous })
  }

  const result = auditLogsQuery.data

  return (
    <ListPageTemplate
      header={
        <ViewHeader
          icon="clipboard"
          title="审计日志"
          description="查询登录、标书编制、成果和账号管理操作。"
          action={
            <Button
              variant="outline"
              size="sm"
              disabled={!result || result.items.length === 0}
              onClick={() => downloadAuditLogs(result?.items ?? [])}
            >
              <Icon name="download" size="sm" />
              导出当前页
            </Button>
          }
        />
      }
      filters={
        <form onSubmit={submitFilters}>
          <FilterBar
            count={`本页 ${result?.items.length ?? 0} 条`}
            onReset={resetFilters}
            resetLabel="重置筛选"
            search={
              <label className="relative block w-full sm:w-panel-sm">
                <Icon
                  name="search"
                  size="sm"
                  className="pointer-events-none absolute left-sm top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  value={draft.keyword}
                  onChange={(event) => setDraft({ ...draft, keyword: event.target.value })}
                  className="pl-xl"
                  placeholder="账号、标书、说明或追踪号"
                />
              </label>
            }
            actions={
              <Button type="submit" variant="outline">
                <Icon name="search" size="sm" />
                查询
              </Button>
            }
          >
            <NativeSelect
              value={draft.actionCode}
              wrapperClassName="w-panel-sm"
              aria-label="操作筛选"
              onChange={(event) => setDraft({ ...draft, actionCode: event.target.value })}
            >
              <option value="">全部操作</option>
              {Object.entries(actionLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect
              value={draft.resultCode}
              wrapperClassName="w-panel-sm"
              aria-label="结果筛选"
              onChange={(event) => setDraft({ ...draft, resultCode: event.target.value })}
            >
              <option value="">全部结果</option>
              <option value="SUCCESS">成功</option>
              <option value="FAILED">失败</option>
              <option value="DENIED">拒绝</option>
            </NativeSelect>
            <Input
              type="date"
              value={draft.startDate}
              aria-label="开始日期"
              onChange={(event) => setDraft({ ...draft, startDate: event.target.value })}
              className="w-panel-sm"
            />
            <Input
              type="date"
              value={draft.endDate}
              aria-label="结束日期"
              onChange={(event) => setDraft({ ...draft, endDate: event.target.value })}
              className="w-panel-sm"
            />
          </FilterBar>
        </form>
      }
      table={
        auditLogsQuery.isError ? (
          <QueryError error={auditLogsQuery.error} retry={() => void auditLogsQuery.refetch()} />
        ) : (
          <DataTable
            columns={columns}
            rows={result?.items ?? []}
            rowKey={(log) => log.eventId}
            loading={auditLogsQuery.isLoading}
            loadingRows={10}
            empty={
              <EmptyState
                icon="clipboard"
                title="没有符合条件的审计记录"
                description="调整筛选条件后重新查询。"
              />
            }
          />
        )
      }
      footer={
        result ? (
          <div className="flex items-center justify-between gap-md">
            <span className="text-sm text-muted-foreground">
              本页 {result.items.length} 条
            </span>
            <div className="flex items-center gap-sm">
              <Button
                variant="outline"
                size="sm"
                disabled={visited.length === 0}
                onClick={goPrevious}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={result.nextCursor === null}
                onClick={() => result.nextCursor && goNext(result.nextCursor)}
              >
                下一页
              </Button>
            </div>
          </div>
        ) : undefined
      }
    />
  )
}
