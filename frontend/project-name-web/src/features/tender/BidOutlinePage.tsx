// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import {
  Banner,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  MetricGrid,
  Progress,
  Spinner,
  ViewHeader,
} from '@vxture/design-system'

import type { OutlineNodeInput } from '@/types/tender'
import { createClientId } from '@/utils/clientId'

import { BidPageShell } from './components/BidPageShell'
import { ErrorState, LoadingState } from './components/Feedback'
import { OutlineWarnings } from './components/OutlineWarnings'
import {
  useBidWorkspaceQuery,
  useGenerateContentMutation,
  useGenerateOutlineMutation,
  useSaveOutlineMutation,
} from './queries'

const outlineStageLabels = {
  QUEUED: '任务已提交，正在排队',
  PREPARING: '正在整理项目概述、技术评分要求和参考素材',
  GENERATING: 'AI 正在编写三级目录',
  SAVING: '正在校验并保存目录',
  COMPLETE: '目录生成完成',
  FAILED: '目录生成失败',
} as const

export default function BidOutlinePage() {
  const { bidId = '' } = useParams()
  const navigate = useNavigate()
  const query = useBidWorkspaceQuery(bidId)
  const generateMutation = useGenerateOutlineMutation(bidId)
  const saveMutation = useSaveOutlineMutation(bidId)
  const contentMutation = useGenerateContentMutation(bidId)
  const [nodes, setNodes] = useState<OutlineNodeInput[]>([])
  const [validation, setValidation] = useState('')

  useEffect(() => {
    if (!query.data) return
    if (['PENDING', 'RUNNING', 'FAILED'].includes(query.data.outlineTask?.status ?? '')) {
      setNodes([])
      return
    }
    setNodes(normalizeTopLevelPageBudgets(query.data.outline.map(toOutlineInput)))
  }, [query.data])

  const totalPages = nodes
    .filter((node) => node.level === 1)
    .reduce((sum, node) => sum + node.plannedPages, 0)

  if (query.isPending) return <LoadingState label="正在读取目录" />
  if (query.error || !query.data)
    return <ErrorState error={query.error ?? new Error('标书不存在')} />
  const workspace = query.data
  const outlineTask = workspace.outlineTask
  const isGenerating = ['PENDING', 'RUNNING'].includes(outlineTask?.status ?? '')
  const generate = async () => {
    setNodes([])
    setValidation('')
    try {
      await generateMutation.mutateAsync(undefined)
    } catch {
      // Error is rendered below the outline.
    }
  }

  const validate = () => {
    if (nodes.length === 0 || nodes.some((node) => !node.title.trim()))
      return '目录不能为空，章节名称必须填写'
    if (nodes.some((node) => node.level === 1 && node.plannedPages < 1))
      return '每个一级章节必须安排计划页数'
    return ''
  }

  const save = async (confirm: boolean) => {
    const error = validate()
    setValidation(error)
    if (error) return
    try {
      await saveMutation.mutateAsync({ nodes, confirm, revision: workspace.bid.revision })
      if (confirm) {
        await contentMutation.mutateAsync(undefined)
        navigate(`/planner/bids/${bidId}/generating`)
      }
    } catch {
      // Error is rendered below the outline.
    }
  }

  const addChild = (parent: OutlineNodeInput) => {
    if (parent.level >= 3) return
    const index = nodes.findIndex((node) => node.clientId === parent.clientId)
    const child: OutlineNodeInput = {
      clientId: createClientId(),
      parentClientId: parent.clientId,
      level: parent.level + 1,
      title: '新建章节',
      plannedPages: 0,
      taskBrief: '',
      mustKeywords: [],
      scoringPointIds: [],
    }
    setNodes((current) => [...current.slice(0, index + 1), child, ...current.slice(index + 1)])
  }

  const removeNode = (nodeId: string) => {
    const removing = new Set([nodeId])
    let changed = true
    while (changed) {
      changed = false
      nodes.forEach((node) => {
        if (
          node.parentClientId &&
          removing.has(node.parentClientId) &&
          !removing.has(node.clientId)
        ) {
          removing.add(node.clientId)
          changed = true
        }
      })
    }
    setNodes((current) => current.filter((node) => !removing.has(node.clientId)))
  }

  return (
    <BidPageShell bid={workspace.bid} current="OUTLINE">
      <div className="mx-auto w-full max-w-content-base-xl px-page-inset py-page-inset">
        <ViewHeader
          icon="tree-structure"
          title="目录编写"
          description="目录最多三级，计划页数仅填写一级章节总页数"
          action={
            <Button
              variant="outline"
              disabled={generateMutation.isPending || isGenerating}
              onClick={() => void generate()}
            >
              {generateMutation.isPending || isGenerating ? (
                <Spinner size="sm" />
              ) : (
                <Icon name="sparkles" size="sm" />
              )}
              {generateMutation.isPending
                ? '正在提交'
                : isGenerating
                  ? '目录生成中'
                  : nodes.length
                    ? '重新生成目录'
                    : '自动生成目录'}
            </Button>
          }
        />

        {isGenerating && outlineTask ? (
          <Banner
            tone="info"
            title={
              <span className="flex items-center gap-xs">
                <Spinner size="sm" />
                {outlineStageLabels[outlineTask.stage]}
              </span>
            }
            description={
              <span className="flex flex-col gap-xs">
                <Progress value={outlineTask.progress} aria-label="目录生成进度" />
                <span>
                  {outlineTask.progress}% · 任务在后台持续执行，可以刷新页面或稍后返回。
                </span>
              </span>
            }
          />
        ) : null}
        <OutlineWarnings task={outlineTask} />

        <MetricGrid
          className="mt-lg"
          columns={3}
          aria-label="目录统计"
          items={[
            { id: 'chapters', label: '目录章节', value: nodes.length, icon: 'tree-structure' },
            { id: 'pages', label: '计划页数', value: totalPages, icon: 'file-text' },
            {
              id: 'difference',
              label: '与预设差值',
              value: `${totalPages - workspace.bid.targetPages > 0 ? '+' : ''}${totalPages - workspace.bid.targetPages}`,
              tone: totalPages === workspace.bid.targetPages ? 'success' : 'warning',
              icon: 'chart-line',
            },
          ]}
        />

        <Card className="mt-lg border border-border">
          <fieldset disabled={isGenerating}>
          <header className="grid grid-cols-12 border-b border-border px-lg py-sm text-label-sm text-muted-foreground">
            <span className="col-span-1 hidden sm:block">层级</span>
            <span className="col-span-7 sm:col-span-6">章节名称</span>
            <span className="col-span-3">一级章节页数</span>
            <span className="col-span-2">操作</span>
          </header>
          {nodes.length === 0 ? (
            <EmptyState
              className="m-lg min-h-row-6xl"
              icon="tree-structure"
              title={isGenerating ? '正在生成新目录' : '尚未生成目录'}
              description={
                isGenerating
                  ? '旧目录已清除，生成完成后将显示新的三级目录'
                  : '系统将根据项目概述和技术部分评分要求生成一版三级目录'
              }
              action={
                !isGenerating ? (
                <Button className="mt-lg" onClick={() => void generate()}>
                  <Icon name="sparkles" size="sm" />
                  自动生成目录
                </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="divide-y divide-border">
              {nodes.map((node) => {
                const root = node.level === 1
                return (
                  <div
                    key={node.clientId}
                    className="grid grid-cols-12 items-center gap-xs px-lg py-sm"
                  >
                    <span className="col-span-1 hidden text-body-sm text-muted-foreground sm:block">
                      L{node.level}
                    </span>
                    <div
                      className="col-span-7 min-w-0 sm:col-span-6"
                      style={{ paddingLeft: `${(node.level - 1) * 18}px` }}
                    >
                      <Input
                        value={node.title}
                        onChange={(event) =>
                          setNodes((current) =>
                            current.map((item) =>
                              item.clientId === node.clientId
                                ? { ...item, title: event.target.value }
                                : item
                            )
                          )
                        }
                      />
                    </div>
                    <Input
                      className="col-span-3"
                      type="number"
                      min={root ? 1 : 0}
                      disabled={!root || isGenerating}
                      value={root ? node.plannedPages : 0}
                      onChange={(event) =>
                        setNodes((current) =>
                          current.map((item) =>
                            item.clientId === node.clientId
                              ? { ...item, plannedPages: root ? Number(event.target.value) : 0 }
                              : item
                          )
                        )
                      }
                    />
                    <div className="col-span-2 flex">
                      {node.level < 3 ? (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="新增子章节"
                          aria-label="新增子章节"
                          onClick={() => addChild(node)}
                        >
                          <Icon name="plus" size="sm" />
                        </Button>
                      ) : null}
                      <Button
                        variant="destructive"
                        confirmExempt="删除仅影响尚未保存的目录，可通过重新生成恢复"
                        size="icon-sm"
                        title="删除章节"
                        aria-label="删除章节"
                        onClick={() => removeNode(node.clientId)}
                      >
                        <Icon name="trash" size="sm" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          </fieldset>
        </Card>

        {validation ? <Banner className="mt-lg" tone="danger" title={validation} /> : null}
        <div className="mt-lg">
          <ErrorState
            error={
              generateMutation.error ??
              saveMutation.error ??
              contentMutation.error ??
              (outlineTask?.status === 'FAILED'
                ? new Error(outlineTask.errorMessage ?? '目录生成失败')
                : null)
            }
          />
        </div>
        <div className="mt-xl flex flex-wrap justify-between gap-sm border-t border-border pt-lg">
          <Button
            variant="outline"
            onClick={() => navigate(`/planner/bids/${bidId}/interpretation`)}
          >
            <Icon name="arrow-left" size="sm" />
            上一步
          </Button>
          <div className="flex flex-wrap gap-xs">
            <Button
              variant="outline"
              disabled={!nodes.length || isGenerating || saveMutation.isPending}
              onClick={() => void save(false)}
            >
              保存目录
            </Button>
            <Button
              disabled={
                !nodes.length || isGenerating || saveMutation.isPending || contentMutation.isPending
              }
              onClick={() => void save(true)}
            >
              {saveMutation.isPending || contentMutation.isPending ? (
              <Spinner size="sm" />
              ) : null}
              确认目录并编写正文
            </Button>
          </div>
        </div>
      </div>
    </BidPageShell>
  )
}

const toOutlineInput = (node: {
  id: string
  parentId: string | null
  level: number
  title: string
  plannedPages: number
  taskBrief: string
  mustKeywords: string[]
  scoringPointIds: string[]
}): OutlineNodeInput => ({
  clientId: node.id,
  parentClientId: node.parentId,
  level: node.level,
  title: node.title,
  plannedPages: node.plannedPages,
  taskBrief: node.taskBrief,
  mustKeywords: node.mustKeywords,
  scoringPointIds: [],
})

const normalizeTopLevelPageBudgets = (nodes: OutlineNodeInput[]) => {
  const byId = new Map(nodes.map((node) => [node.clientId, node]))
  const legacyPages = new Map<string, number>()
  nodes.forEach((node) => {
    if (node.level === 1 || node.plannedPages <= 0) return
    const visited = new Set<string>()
    let current: OutlineNodeInput | undefined = node
    while (
      current &&
      current.level > 1 &&
      current.parentClientId &&
      !visited.has(current.clientId)
    ) {
      visited.add(current.clientId)
      current = byId.get(current.parentClientId)
    }
    if (current?.level === 1) {
      legacyPages.set(
        current.clientId,
        (legacyPages.get(current.clientId) ?? 0) + node.plannedPages
      )
    }
  })
  return nodes.map((node) => ({
    ...node,
    plannedPages:
      node.level === 1 ? Math.max(node.plannedPages, legacyPages.get(node.clientId) ?? 0) : 0,
  }))
}
