// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { Stack } from '@vxture/design-ui'

import type { AccessState } from '@/features/entitlement/access'

import { GateActions, GatePrimary, GatePrimaryButton, GateSignOut } from './gate-actions'
import { GateFrame } from './gate-frame'
import { GateHeading } from './gate-heading'
import { GateIdentity, type GateIdentityProps } from './gate-identity'

import { useLocale, useMessages } from '../lib/i18n/use-messages'

// 已登录、当前工作区没有可用订阅（参照 vx-agent-yucer app/(app)/components/no-subscription.tsx）。
//
// 与引导页是两张页面，因为读者不同：他已经通过认证，产品知道他是谁。所以说出只有产品能给的两件事——
// 谁在登录、被拒的是哪个工作区（管理员据此行动，走错工作区的成员据此发现自己走错了）——再给订阅的路与退出的路。
//
// 标题说的是工作区，不是产品码：读者没有选过产品码，也未必认得它。
//
// 身份块不是 yucer 的两列 LabeledValue（owner 2026-09-16）：真实名字在两列里被截断，见 gate-identity.tsx。
//
// 本产品比 yucer 多三种被拒的原因，形状完全一样，只换状态标签、一句话与主动作：
// 订阅失效（前往续订，带出数据保留期）、档位不认得（查看订阅）、平台暂时没答上来（重试——
// 这不代表没订阅，不能给订阅入口）。判定不在这里：这个组件只渲染它拿到的拒绝。

export type BlockedAccess = Exclude<AccessState, { kind: 'granted' }>

export function NoSubscription({
  access,
  subscribeHref,
  identity,
  onRetry,
  retrying = false,
}: {
  readonly access: BlockedAccess
  /** 服务端按权益拼好的控制台深链；从来不在这里推导。 */
  readonly subscribeHref: string | null
  readonly identity: GateIdentityProps
  readonly onRetry: () => void
  readonly retrying?: boolean
}) {
  const { SHELL_TEXT, NO_SUBSCRIPTION_TEXT: T } = useMessages()
  const locale = useLocale()

  const copy = (() => {
    switch (access.kind) {
      case 'never-subscribed':
        return { badge: T.badge, title: SHELL_TEXT.noAccessTitle, description: T.description, cta: SHELL_TEXT.subscribeCta }
      case 'lapsed': {
        const status = T.statusLabels[access.status.trim().toLowerCase()] ?? access.status
        const retention = access.dataRetentionUntil ? ` ${T.retentionUntil(formatDate(access.dataRetentionUntil, locale))}` : ''
        return { badge: T.lapsedBadge(status), title: T.lapsedTitle, description: T.lapsedDescription + retention, cta: T.renewCta }
      }
      case 'unknown-tier':
        return {
          badge: T.unknownTierBadge,
          title: T.unknownTierTitle,
          description: T.unknownTierDescription(access.tier),
          cta: T.viewSubscriptionCta,
        }
      case 'unavailable':
        return { badge: T.unavailableBadge, title: T.unavailableTitle, description: T.unavailableDescription, cta: null }
    }
  })()

  const primary =
    copy.cta && subscribeHref ? (
      <GatePrimary href={subscribeHref} external>
        {copy.cta}
      </GatePrimary>
    ) : (
      <GatePrimaryButton onClick={onRetry} disabled={retrying}>
        {T.retry}
      </GatePrimaryButton>
    )

  return (
    <GateFrame ariaLabel={T.ariaLabel} width="narrow">
      <Stack gap="lg" className="items-center">
        <GateHeading badge={copy.badge} badgeIcon="credit-card" title={copy.title} description={copy.description} />

        <GateIdentity {...identity} />

        <GateActions primary={primary} secondary={<GateSignOut>{T.signOut}</GateSignOut>} />
      </Stack>
    </GateFrame>
  )
}

function formatDate(value: string, locale: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(locale)
}
