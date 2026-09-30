// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { useEffect } from 'react'

import { Stack } from '@vxture/design-ui'

import { GateActions, GatePrimary, GateSecondary } from './gate-actions'
import { GateFrame } from './gate-frame'
import { GateHeading } from './gate-heading'

import { clearSignedOutMarker } from '../auth/signed-out-marker'
import { useMessages } from '../lib/i18n/use-messages'

// 退出登录之后（参照 vx-agent-yucer app/(app)/components/signed-out.tsx，照搬）。
//
// 由 IdP 的退出回跳送来，落在产品根路径——与引导页同一个地址，因为平台登记的就是它。
// 没有这一页，产品会用「登录」回应一次主动退出，读者分不清退出是成功了还是失败了。
//
// 标题上方没有打勾的圆：那是表单确认「可能失败的事成功了」的形状，退出不是；那句话本身就是确认。
// 下面那一行是读者自己不知道的唯一一件事：产品结束了自己的会话，管不了浏览器的。

export function SignedOut({ consoleHref }: { readonly consoleHref: string | null }) {
  const { SIGNED_OUT_TEXT } = useMessages()

  // 在这里消费便条：挂载时清掉，只显示一次。等它自己过期的话，读者下一次打开的地址还会回以一张已经读过的退出通知。
  useEffect(() => {
    clearSignedOutMarker()
  }, [])

  return (
    <GateFrame ariaLabel={SIGNED_OUT_TEXT.ariaLabel} width="narrow">
      <Stack gap="lg" className="items-center">
        <GateHeading title={SIGNED_OUT_TEXT.title} description={SIGNED_OUT_TEXT.description} />

        <GateActions
          // 裸路由，不带回跳：读者选择离开，回来的地方是产品的起点，而不是退出时停在的那一页。
          primary={<GatePrimary href="/api/auth/oidc/login">{SIGNED_OUT_TEXT.signInAgain}</GatePrimary>}
          // 只在配置了控制台时出现——一个哪里都不去的按钮比没有按钮更糟。
          secondary={
            consoleHref ? <GateSecondary href={consoleHref}>{SIGNED_OUT_TEXT.toConsole}</GateSecondary> : undefined
          }
        />
      </Stack>
    </GateFrame>
  )
}
