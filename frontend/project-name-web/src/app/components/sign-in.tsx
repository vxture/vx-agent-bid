// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { useLocation } from 'react-router'

import { Button, Stack } from '@vxture/design-ui'

import { GateFrame } from './gate-frame'
import { GateHeading } from './gate-heading'

import { loginHref } from '../auth/return-to'
import { useMessages } from '../lib/i18n/use-messages'

// 产品的前门（参照 vx-agent-yucer app/(app)/components/sign-in.tsx，照搬）。
//
// 输入域名进来、以及没有会话打开任何路由，都到这里——所以就地渲染而不是重定向：
// 重定向到 IdP 会把只是打开了一个旧标签页的人弹走；就地渲染保留地址，回跳就能带上他要去的那一页。
//
// 这里只剩中段：产品名与标识是框架的上段，流程是下段。一句话、一条进门的路，这就是门——
// 产品介绍在官网，页头有链接过去。

export function SignIn() {
  const { SIGNIN_TEXT } = useMessages()
  // 取路由的地址而不是 window.location：引导页总在路由里渲染，两者在浏览器里一致，在内存路由里只有前者对。
  const href = loginHref(useLocation())

  return (
    <GateFrame ariaLabel={SIGNIN_TEXT.ariaLabel} width="wide">
      <Stack gap="lg" className="items-center">
        <GateHeading title={SIGNIN_TEXT.title} description={SIGNIN_TEXT.description} />

        <Button asChild size="xl" className="min-w-[240px]">
          <a href={href}>{SIGNIN_TEXT.cta}</a>
        </Button>
      </Stack>
    </GateFrame>
  )
}
