// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import type { ReactNode } from 'react'

import { type IconName, StatusBadge } from '@vxture/design-ui'

// 每张门禁页中段开头的标题块（参照 vx-agent-yucer app/(app)/components/gate-heading.tsx，照搬）。
//
// 四张一个形状：一句陈述，下面一行，状态标签领起这一行。
//
// 标签在第二行文字前面，不挂在标题旁边：标签是正文字号，标题不是，挂在标题旁边没有可对齐的东西；
// 放在它领起的那一行，与那句话同高，读起来就是它本来的意思——先是状态，再是该怎么办。

export function GateHeading({
  badge,
  badgeIcon,
  title,
  description,
}: {
  /** 状态，作为标题下一行开头的短标签。没有状态可说时不传——引导页与已退出页不传。 */
  readonly badge?: ReactNode
  readonly badgeIcon?: IconName
  readonly title: ReactNode
  readonly description?: ReactNode
}) {
  return (
    <div className="gap-sm flex flex-col items-center text-center">
      <h1 className="text-heading-2 text-balance">{title}</h1>

      {(badge || description) && (
        <p className="gap-sm text-body-md text-muted-foreground flex flex-wrap items-center justify-center">
          {badge && (
            <StatusBadge tone="info" icon={badgeIcon}>
              {badge}
            </StatusBadge>
          )}
          {description}
        </p>
      )}
    </div>
  )
}
