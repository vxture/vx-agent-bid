// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { Stack } from '@vxture/design-ui'

import { GateActions, GatePrimary, GateSignOut } from './gate-actions'
import { GateFrame } from './gate-frame'
import { GateHeading } from './gate-heading'
import { GateIdentity, type GateIdentityProps } from './gate-identity'

import { useMessages } from '../lib/i18n/use-messages'

// 工作区已订阅、成员还没有角色（参照 vx-agent-yucer app/(app)/components/no-roles.tsx，照搬）。
//
// 与「未订阅」同一个形状。它是唯一一张读者自己无能为力的门禁页，所以那一行说出该找谁——
// 开通订阅的人（平台 workspace:owner，本产品的 ADMIN）。身份放在页面上，因为那位管理员要在名单里找这个人；
// 走错工作区也会得到这一页，工作区名一眼就能说清。身份块与「未订阅」共用 gate-identity.tsx（owner 2026-09-16）。
//
// 没有订阅按钮：已经付过钱的工作区不能靠再付一次来补一个角色。
//
// 本产品眼下没有这个状态（每个成员都是 ADMIN 或 PLANNER），这一页在预览里可见，等有了判定直接接上。

export function NoRoles({ identity }: { readonly identity: GateIdentityProps }) {
  const { SHELL_TEXT, NO_ROLES_TEXT } = useMessages()

  return (
    <GateFrame ariaLabel={NO_ROLES_TEXT.ariaLabel} width="narrow">
      <Stack gap="lg" className="items-center">
        {/* 钥匙，因为说的是访问：工作区付过钱、门是真的，这个成员还没拿到开门的东西。 */}
        <GateHeading
          badge={NO_ROLES_TEXT.badge}
          badgeIcon="key"
          title={SHELL_TEXT.noRolesTitle}
          description={SHELL_TEXT.noRolesDescription}
        />

        <GateIdentity {...identity} />

        {/* 主动作就是重新加载：角色来自别处（另一个会话里的管理员），没有可轮询的东西，再问一次就是全部机制。 */}
        <GateActions
          primary={<GatePrimary href="/">{NO_ROLES_TEXT.recheck}</GatePrimary>}
          secondary={<GateSignOut>{NO_ROLES_TEXT.signOut}</GateSignOut>}
        />
      </Stack>
    </GateFrame>
  )
}
