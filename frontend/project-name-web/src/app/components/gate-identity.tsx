// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-16
import { Card, Icon, UserAvatar } from '@vxture/design-ui'

import { useMessages } from '../lib/i18n/use-messages'

// 门禁页上「谁在登录、在哪个工作区」的身份块（owner 2026-09-16）。
//
// 人员、单位左右两项，都不带标签——内容自己说明是什么；两边都是「图 + 两行」，读起来对称：
// - 人员（左）：头像 + 名字，名字下面是联系方式（手机号，没有时邮箱）。头像是平台签发的 picture；
//   没有时 UserAvatar 自己画默认剪影，不渲染空 <img>。
// - 单位（右）：组织图标 + 组织名，下面是工作区名。
//
// 为什么不照搬 yucer 的两列 LabeledValue：真实的「组织 / 工作区」塞进一个读数里会被截断，截掉的正好是
// 工作区名——读者最需要的那一半（yucer 只显示兜底短文案，所以没暴露）。这里每一行各自换行，不截断。
//
// 组织图标是设计系统的 building，不是组织自己的 logo：平台的组织 logo 目前只由控制台在它自己的会话里提供，
// token 里没有，本产品取不到。平台给出 RP 可取的地址之后，换成组织 logo 只改这一处。

export interface GateIdentityProps {
  readonly userName: string
  /** 平台 picture（https）；null 时显示默认剪影。 */
  readonly avatarSrc: string | null
  /** 名字下面一行：手机号，没有时邮箱；都没有时为 null，只显示名字。 */
  readonly contact: string | null
  /** 平台没给、或与工作区同名时为 null，只显示工作区一行。 */
  readonly orgName: string | null
  readonly workspaceName: string
}

const PRIMARY_LINE = 'text-body-md font-medium break-words'
const SECONDARY_LINE = 'text-body-md text-muted-foreground break-words'

export function GateIdentity({ userName, avatarSrc, contact, orgName, workspaceName }: GateIdentityProps) {
  const { SHELL_TEXT } = useMessages()

  return (
    <Card
      surface="soft"
      role="group"
      aria-label={SHELL_TEXT.identityCardLabel}
      className="gap-md p-lg grid w-full grid-cols-2 text-left"
    >
      <div className="gap-sm flex min-w-0 items-center">
        <UserAvatar src={avatarSrc} alt={userName} className="size-10 shrink-0" />
        <div className="min-w-0">
          <p className={PRIMARY_LINE}>{userName}</p>
          {contact && <p className={SECONDARY_LINE}>{contact}</p>}
        </div>
      </div>

      <div className="gap-sm flex min-w-0 items-center">
        <span
          aria-hidden
          className="bg-muted text-muted-foreground flex size-10 shrink-0 items-center justify-center rounded-full"
        >
          <Icon name="building" size="sm" />
        </span>
        <div className="min-w-0">
          {orgName && <p className={PRIMARY_LINE}>{orgName}</p>}
          <p className={orgName ? SECONDARY_LINE : PRIMARY_LINE}>{workspaceName}</p>
        </div>
      </div>
    </Card>
  )
}
