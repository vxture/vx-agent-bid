// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { useState } from 'react'

import { SegmentedControl } from '@vxture/design-ui'

import type { GateIdentityProps } from '../components/gate-identity'
import { NoRoles } from '../components/no-roles'
import { NoSubscription } from '../components/no-subscription'
import { SignIn } from '../components/sign-in'
import { SignedOut } from '../components/signed-out'
import { useMessages } from '../lib/i18n/use-messages'

// 四张门禁页的预览，不需要会话，也不需要平台（参照 vx-agent-yucer app/(demo)/gate-screens/page.tsx，照搬）。
//
// 为什么要一个预览路由：四张页各自回答一种不同的缺失——没会话、没订阅、没角色、刚退出——
// 在产品里看到它们就得分别凑出四个按构造互斥的状态。这里只有示例数据，没有会话、没有数据库。
//
// 语言跟着页头切换器写的 cookie 走（词典 Provider 读它），审阅者看到的是自己选的语言。

type Screen = 'sign-in' | 'no-subscription' | 'no-roles' | 'signed-out'

const SAMPLE_SUBSCRIBE_URL = 'https://vxture.com/pricing?product=tenderforge'
const SAMPLE_CONSOLE_URL = 'https://console.vxture.com'

export default function GateScreensPreview() {
  const { GATE_PREVIEW_TEXT } = useMessages()
  const [screen, setScreen] = useState<Screen>('sign-in')

  // 没有头像：预览里看到的是默认剪影，正是没设头像的成员会看到的样子。
  const identity: GateIdentityProps = {
    userName: GATE_PREVIEW_TEXT.sampleUser,
    avatarSrc: null,
    contact: '138 0000 1234',
    orgName: GATE_PREVIEW_TEXT.sampleOrg,
    workspaceName: GATE_PREVIEW_TEXT.sampleWorkspace,
  }

  return (
    <>
      {/* 浮在被审阅的页面上而不是把它往下推：每张都是满视口，选择器占在流里就没有一张以发布尺寸被看到。
          放在底部，因为顶部是产品标识的位置——手机上两者会撞。 */}
      <div className="p-sm fixed inset-x-0 bottom-0 z-50 flex justify-center">
        <div className="bg-card/90 border-border gap-sm p-xs flex items-center rounded-full border shadow-sm backdrop-blur">
          <SegmentedControl
            size="sm"
            ariaLabel={GATE_PREVIEW_TEXT.ariaLabel}
            value={screen}
            onChange={setScreen}
            items={[
              { value: 'sign-in', label: GATE_PREVIEW_TEXT.signIn },
              { value: 'no-subscription', label: GATE_PREVIEW_TEXT.noSubscription },
              { value: 'no-roles', label: GATE_PREVIEW_TEXT.noRoles },
              { value: 'signed-out', label: GATE_PREVIEW_TEXT.signedOut },
            ]}
          />
        </div>
      </div>

      {screen === 'sign-in' && <SignIn />}
      {screen === 'no-subscription' && (
        <NoSubscription
          access={{ kind: 'never-subscribed' }}
          subscribeHref={SAMPLE_SUBSCRIBE_URL}
          identity={identity}
          onRetry={() => undefined}
        />
      )}
      {screen === 'no-roles' && <NoRoles identity={identity} />}
      {screen === 'signed-out' && <SignedOut consoleHref={SAMPLE_CONSOLE_URL} />}
    </>
  )
}
