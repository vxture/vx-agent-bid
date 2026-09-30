// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
import type { ReactNode } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
  Button,
  Card,
  Icon,
  Section,
  ShellPageContainer,
  StatusBadge,
  ViewHeader,
} from '@vxture/design-system'

import { MutationError, QueryError, QueryLoading } from '@/components/QueryState'
import type { PlatformProbe, PlatformSpendResult } from '@/types/admin'

import { formatDateTime } from './formatters'
import {
  useAtlasProbeMutation,
  usePlatformCheckQuery,
  useUsageReplayProbeMutation,
} from './queries'

/**
 * 系统验证：本产品这一端与平台的对接，现在通不通。
 *
 * 版式照 yucer 的「系统验证」：只读探测一次全跑、全部免费；会花钱的两项各自单独成卡，
 * 必须经确认对话框才能触发——误点一下不能花钱。按「分节」组织而不是一张平铺清单，
 * 第二类系统验证到来时是多写一节，而不是改版这一页。
 *
 * `/api/status` 报「配没配」，这里报「通不通」：配齐了而换票被拒、票铸出来而 Atlas 不认、
 * 权益端点答了但答的是「未覆盖」——这些都只有真打一次才看得见。
 */
export default function DiagnosticsPage() {
  const check = usePlatformCheckQuery()
  const atlasProbe = useAtlasProbeMutation()
  const replayProbe = useUsageReplayProbeMutation()

  return (
    <section className="min-h-0 flex-1 overflow-y-auto" aria-label="系统验证">
      <ShellPageContainer width="base-xl">
        <ViewHeader
          icon="plugs-connected"
          title="系统验证"
          description="产品这一端与平台的对接是否健康。只读探测不产生费用，会花钱的动作各自单独标出。"
        />

        <div className="mb-md flex items-center justify-between gap-md">
          <p className="text-body-sm text-muted-foreground">
            {check.data ? `探测时间 ${formatDateTime(check.data.time)}` : '正在探测…'}
          </p>
          <Button
            variant="outline"
            size="sm"
            disabled={check.isFetching}
            onClick={() => void check.refetch()}
          >
            <Icon name="refresh" size="sm" />
            {check.isFetching ? '探测中…' : '重新探测'}
          </Button>
        </div>

        {check.isPending ? <QueryLoading label="正在逐项探测" /> : null}
        {check.isError ? <QueryError error={check.error} retry={() => void check.refetch()} /> : null}

        {check.data ? (
          <div className="flex flex-col gap-xl">
            <Section
              icon="plugs-connected"
              title="平台对接"
              description="身份（C1）、换票（C1b）、权益（C2）、用量上报与开通（C3）"
            >
              <p className="mb-sm text-body-sm text-muted-foreground">
                以下探测全部只读，不产生任何费用
              </p>
              <div className="grid grid-cols-1 gap-md md:grid-cols-2 xl:grid-cols-3">
                <ProbeCard title="C1 · 身份发现与密钥" probe={check.data.c1} />
                <ProbeCard title="C1b · S2S 换票" probe={check.data.tokenMint} />
                <ProbeCard title="C2 · 实时权益读取" probe={check.data.c2} />
                <ProbeCard title="C3 上行 · 用量上报" probe={check.data.c3Up} />
                <ProbeCard title="C3 下行 · 开通 webhook" probe={check.data.c3Down} />
              </div>
              <div className="mt-md">
                <SpendingProbeCard
                  title="C3 重放校验"
                  hint="把同一条用量记录上报两次，核实平台按幂等键去重而不是重复计费。每个工作空间每天最多记一笔。"
                  currentDetail={check.data.usageReplay.detail}
                  result={replayProbe.data ?? null}
                  error={replayProbe.error}
                  running={replayProbe.isPending}
                  runLabel="运行重放校验"
                  confirmTitle="确认运行重放校验？"
                  confirmBody="这会向平台实际发送一条用量记录（今天第一次运行才会真正记账，同一天重复运行命中同一个幂等键）。"
                  onConfirm={() => replayProbe.mutate()}
                />
              </div>
            </Section>

            <Section
              icon="cpu"
              title="模型出口（Atlas）"
              description="本产品唯一的模型出口。票由后端现铸，与生成正文走同一条链路"
            >
              <div className="grid grid-cols-1 gap-md md:grid-cols-2">
                <ProbeCard title="带票读取模型清单" probe={check.data.atlas} />
                <ProbeCard title="路由容量与推理模式" probe={check.data.atlasRoutes} />
              </div>
              <div className="mt-md">
                <SpendingProbeCard
                  title="Atlas 活体探测"
                  hint="对本产品实际使用的每条路由各发一次最短的对话，验证授权、模型挂载与计量链路都是通的。消耗由 Atlas 按其计量口径自行上报，不经过本产品的用量指标。"
                  currentDetail="尚未运行。只读探测只能证明票被 Atlas 认，证明不了某条路由真的能完成一次调用。"
                  result={atlasProbe.data ?? null}
                  error={atlasProbe.error}
                  running={atlasProbe.isPending}
                  runLabel="运行 Atlas 探测"
                  confirmTitle="确认运行 Atlas 探测？"
                  confirmBody="这会向 Atlas 实际发起几次模型调用（每条路由一次，补全上限 8 个 token），产生真实的模型用量。"
                  onConfirm={() => atlasProbe.mutate()}
                />
              </div>
            </Section>
          </div>
        ) : null}
      </ShellPageContainer>
    </section>
  )
}

function badge(probe: PlatformProbe) {
  if (!probe.configured) return <StatusBadge tone="neutral">未配置</StatusBadge>
  return probe.ok ? (
    <StatusBadge tone="success">正常</StatusBadge>
  ) : (
    <StatusBadge tone="danger">异常</StatusBadge>
  )
}

function ProbeCard({ title, probe }: { title: string; probe: PlatformProbe }) {
  return (
    <Card className="border border-border p-md" surface="base">
      <div className="flex items-start justify-between gap-sm">
        <p className="text-body-sm font-medium text-foreground">{title}</p>
        {badge(probe)}
      </div>
      <p className="mt-xs break-words text-body-sm text-muted-foreground">{probe.detail}</p>
    </Card>
  )
}

function SpendingProbeCard({
  title,
  hint,
  currentDetail,
  result,
  error,
  running,
  runLabel,
  confirmTitle,
  confirmBody,
  onConfirm,
}: {
  title: string
  hint: string
  currentDetail: string
  result: PlatformSpendResult | null
  error: unknown
  running: boolean
  runLabel: string
  confirmTitle: string
  confirmBody: string
  onConfirm: () => void
}): ReactNode {
  return (
    <Card className="border border-dashed border-border p-md" surface="base">
      <div className="flex flex-wrap items-start justify-between gap-md">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-xs">
            <p className="text-body-sm font-medium text-foreground">{title}</p>
            <StatusBadge tone="warning">会产生费用</StatusBadge>
            {result ? badge({ configured: true, ok: result.ok, detail: result.detail }) : null}
          </div>
          <p className="mt-2xs max-w-prose text-body-sm text-muted-foreground">{hint}</p>
          <p className="mt-sm break-words text-body-sm text-foreground">
            {result ? result.detail : currentDetail}
          </p>
          {result && result.items.length > 0 ? (
            <ul className="mt-xs flex flex-col gap-2xs">
              {result.items.map((item) => (
                <li key={item.detail} className="flex items-start gap-xs text-body-sm">
                  <Icon
                    name={item.ok ? 'check' : 'x'}
                    size="sm"
                    className={item.ok ? 'text-success' : 'text-danger'}
                  />
                  <span className="break-words text-muted-foreground">{item.detail}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <MutationError error={error} />
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="secondary" size="sm" disabled={running}>
              {running ? '运行中…' : runLabel}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{confirmTitle}</AlertDialogTitle>
              <AlertDialogDescription>{confirmBody}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction onClick={onConfirm}>确认运行</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Card>
  )
}
