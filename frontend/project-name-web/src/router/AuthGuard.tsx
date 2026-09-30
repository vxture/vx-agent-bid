// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-07-29
import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useQuery } from '@tanstack/react-query'
import { ShellBootScreen } from '@vxture/design-system'

import { authApi } from '@/api/modules/auth'
import { hasSignedOutMarker } from '@/app/auth/signed-out-marker'
import { SignIn } from '@/app/components/sign-in'
import { SignedOut } from '@/app/components/signed-out'
import { consoleUrl } from '@/app/lib/console-url'
import { useMessages } from '@/app/lib/i18n/use-messages'
import { useAuthStore } from '@/stores/auth'

interface AuthGuardProps {
  children: React.ReactNode
}

/**
 * 是否已登录，由<b>服务端</b>裁定，不由 localStorage 里有没有一个字符串裁定。
 *
 * 这不只是重构：平台 RP 会话装在 HttpOnly cookie 里，浏览器<b>读不到它</b>，
 * 所以「本地有没有 token」根本回答不了这个问题——OIDC 登录回来后 localStorage
 * 是空的，而用户确实已经登录了。反过来，一个过期的本地 token 会让守卫放行，
 * 然后每个业务请求各自 401 一次。
 *
 * 代价是每次进受保护路由要问一次服务端（react-query 缓存 60 秒）。
 *
 * 没有会话时就地渲染门禁页、不重定向（门禁页规范，参照 yucer 的布局）：保留地址，登录回来就是
 * 读者要去的那一页。刚退出的人与从没登录过的人落在同一个地址、同样没有会话——读到已退出便条就给确认页，
 * 否则给引导页。便条在挂载时读一次并记住：确认页挂载后会把它清掉，守卫之后重渲染时不能因此换成引导页。
 */
export default function AuthGuard({ children }: AuthGuardProps) {
  const location = useLocation()
  const { SHELL_TEXT } = useMessages()
  const [justSignedOut] = useState(hasSignedOutMarker)
  const user = useAuthStore((state) => state.user)
  const setUser = useAuthStore((state) => state.setUser)
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const currentUser = useQuery({
    queryKey: ['current-user'],
    queryFn: authApi.me,
    retry: false,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (currentUser.data) setUser(currentUser.data)
    if (currentUser.isError) clearAuth()
  }, [clearAuth, currentUser.data, currentUser.isError, setUser])

  if (currentUser.isError) {
    return justSignedOut ? <SignedOut consoleHref={consoleUrl()} /> : <SignIn />
  }
  if (currentUser.isPending) {
    return (
      <ShellBootScreen
        label={SHELL_TEXT.brandName}
        description="正在确认登录状态"
        delayMs={250}
      />
    )
  }

  const resolvedUser = currentUser.data ?? user
  if (location.pathname.startsWith('/console') && !resolvedUser?.admin) {
    return <Navigate to="/403" replace />
  }
  return <>{children}</>
}
