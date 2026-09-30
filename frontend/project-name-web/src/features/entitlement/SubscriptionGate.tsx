// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { type ReactNode, useEffect } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ShellBootScreen } from '@vxture/design-system'

import { entitlementApi } from '@/api/modules/entitlement'
import { NoSubscription } from '@/app/components/no-subscription'
import { useMessages } from '@/app/lib/i18n/use-messages'
import { useAuthStore } from '@/stores/auth'
import { platformAvatarSrc } from '@/utils/avatar'

import { accessState } from './access'
import { contactLineOf, identityLabelOf, workspaceLinesOf } from './identity'
import { entitlementKeys, useEntitlementQuery } from './queries'

/**
 * 订阅闸门：已登录不等于能用。进入产品界面之前按 C2 权益判定，没有就停在「当前工作区未订阅」这张门禁页。
 *
 * - 只挡界面，不替代服务端判定：命令入口的 `EntitlementGuard` 仍是强制点。这里挡的是
 *   「进得去、处处 403」——2026-09-15 生产上未订阅用户登录后直接进了智能体。
 * - 门禁页不渲染产品外壳（门禁页规范）：闸门包在整个布局外面，而不是内容区里。
 * - 深链只在显式点击时新开窗口打开，永不自动跳转（通则 C2）。
 * - 切回这个标签页时调 `POST /api/entitlement/refresh`：订阅在控制台的另一个标签页完成，
 *   服务端先驱逐自己工作空间的缓存再问平台，不让刚付完钱的人再看 45 秒旧答案。门禁页按规范只有
 *   一个主动作一条出路，所以原来的「我已完成订阅」按钮换成了切回即重问。
 */
export function SubscriptionGate({ children }: { children: ReactNode }) {
  const entitlement = useEntitlementQuery()
  const queryClient = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const { SHELL_TEXT } = useMessages()
  const recheck = useMutation({
    mutationFn: entitlementApi.refresh,
    onSuccess: (view) => queryClient.setQueryData(entitlementKeys.current, view),
    onError: () => entitlement.refetch(),
  })

  const access = entitlement.isError ? ({ kind: 'unavailable' } as const) : accessState(entitlement.data)
  const blocked = !entitlement.isPending && access.kind !== 'granted'
  const { mutate, isPending: rechecking } = recheck

  useEffect(() => {
    if (!blocked) return
    const onFocus = () => {
      if (!rechecking) mutate()
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [blocked, mutate, rechecking])

  if (entitlement.isPending) {
    return <ShellBootScreen label={SHELL_TEXT.brandName} description="正在确认订阅状态" delayMs={250} />
  }
  if (access.kind === 'granted') return <>{children}</>

  return (
    <NoSubscription
      access={access}
      subscribeHref={entitlement.data?.subscribeUrl ?? null}
      identity={{
        userName: identityLabelOf(user),
        avatarSrc: platformAvatarSrc(user?.avatarUrl),
        contact: contactLineOf(user),
        ...workspaceLinesOf(user, SHELL_TEXT.workspaceFallback),
      }}
      onRetry={() => mutate()}
      retrying={rechecking || entitlement.isFetching}
    />
  )
}
