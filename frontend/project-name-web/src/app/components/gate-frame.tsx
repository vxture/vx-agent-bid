// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import type { ReactNode } from 'react'

import {
  ShellBrand,
  ShellFullscreenToggle,
  ShellIconGroup,
  ShellLocaleSwitcher,
  ShellThemeToggle,
  useTheme,
} from '@vxture/design-system'
import { Button, Icon } from '@vxture/design-ui'
import { type Locale, LOCALE_CONFIGS, SUPPORTED_LOCALES } from '@vxture/shared'

import { BRAND_MARK_SRC, BRAND_WORDMARK, PRODUCT_MARK_SRC } from '../lib/brand-assets'
import { useLocale, useMessages, useSetLocale } from '../lib/i18n/use-messages'
import { websiteUrl } from '../lib/website-url'

// 四张门禁页共用的框架（门禁页规范；参照 vx-agent-yucer app/(app)/components/gate-frame.tsx，照搬）。
//
// 哪四张：未登录引导页（无会话）、当前工作区未订阅（有会话、无可用订阅）、还没有为你分配角色、
// 已退出登录。它们都不渲染产品外壳——没有可导航的东西——各写各的，四张页面会读起来像四个产品。
//
// 三段式，上下两段不动。上段是产品标识，下段是产品自己的信息带，中段才是这一页要说的话；切换页面只动中段。
//
// 页头是公司的，不是产品的。尺寸在 vxture.com 上量出来：行高 64px，容器居中、宽度 1280 → 1536 → 1600，
// 边距到 32px。右侧三个 DS 外壳件加一个指向官网的主按钮。语言切换器必须在这里：它平时只活在产品外壳的
// 偏好面板里，而这几页恰恰没有外壳。
//
// 与 yucer 的差别只在语言切换的落点：yucer 写 cookie 后让服务端重新渲染，本产品没有服务端渲染，
// 由词典 Provider 写 cookie 并就地重渲染。

/** 中段宽度。引导页需要空间；拒绝页是一栏。 */
export type GateWidth = 'narrow' | 'wide'

// 显式像素上限，不用 max-w-lg / max-w-2xl：DS 在这些名字上注册了自己的尺度，max-w-xl 解析出来是 32px。
const WIDTHS: Record<GateWidth, string> = {
  narrow: 'max-w-[452px]',
  wide: 'max-w-[760px]',
}

/** 全屏切换需要一个要全屏的东西。 */
const ROOT_ID = 'gate-root'

export function GateFrame({
  ariaLabel,
  width = 'narrow',
  children,
}: {
  readonly ariaLabel: string
  readonly width?: GateWidth
  readonly children: ReactNode
}) {
  const { SHELL_TEXT, SIGNIN_TEXT, HEADER_TEXT } = useMessages()
  const locale = useLocale()
  const setLocale = useSetLocale()
  const { mode, setMode } = useTheme()
  const site = websiteUrl()

  return (
    <div
      id={ROOT_ID}
      className="bg-background text-foreground relative flex min-h-screen flex-col overflow-hidden"
    >
      <Ambience />

      <header className="relative">
        <div className="gap-md px-md sm:px-lg lg:px-xl mx-auto flex h-16 w-full max-w-[1280px] items-center justify-between xl:max-w-[1536px] 2xl:max-w-[1600px]">
          <ShellBrand href="/" logoSrc={BRAND_MARK_SRC} label={BRAND_WORDMARK} />

          <div className="gap-sm flex items-center">
            <ShellIconGroup label={HEADER_TEXT.prefTitle}>
              <ShellThemeToggle
                currentTheme={mode === 'dark' ? 'dark' : 'light'}
                buttonLabel={HEADER_TEXT.prefTheme}
                lightLabel={HEADER_TEXT.prefThemeLight}
                darkLabel={HEADER_TEXT.prefThemeDark}
                onThemeChange={(next) => setMode(next === 'dark' ? 'dark' : 'light')}
              />
              <ShellLocaleSwitcher
                currentLocale={locale}
                // 语言目录是平台的，不是设计包的；与外壳偏好面板同一份映射。
                options={SUPPORTED_LOCALES.map((l) => ({
                  locale: l,
                  label: LOCALE_CONFIGS[l].nativeName,
                  nativeName: LOCALE_CONFIGS[l].nativeName,
                  flag: LOCALE_CONFIGS[l].flag,
                }))}
                buttonLabel={HEADER_TEXT.prefLocale}
                panelLabel={HEADER_TEXT.prefLocale}
                onLocaleChange={(next) => setLocale(next as Locale)}
              />
              <ShellFullscreenToggle
                targetId={ROOT_ID}
                enterLabel={HEADER_TEXT.fullscreen}
                exitLabel={HEADER_TEXT.fullscreenExit}
              />
            </ShellIconGroup>

            {/* 只有显式把变量置空时才没有：一个哪里都不去的按钮比没有按钮更糟。 */}
            {site && (
              <Button asChild size="sm">
                <a href={site}>{SHELL_TEXT.website}</a>
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* 三段。间距取 token 档位而不是整数——3xl 48、4xl 56、6xl 80——而且刻意宽松：
          产品标识不贴页头，信息带不贴地面（下面 80 + 56）。 */}
      <div className="px-lg pb-4xl relative flex flex-1 flex-col items-center">
        <div className="pt-6xl pb-3xl">
          <ProductIdentity name={SHELL_TEXT.brandName} />
        </div>

        {/* 中段，唯一会变的一段。
            不居中：下方留白是上方的两倍，内容落在视觉中线之上。两个撑杆而不是算出来的高度，
            比例在任何视口都成立，内容仍然拿到它需要的空间。 */}
        <main className="flex w-full flex-1 flex-col items-center">
          <div className="flex-1" />
          <section aria-label={ariaLabel} className={`w-full ${WIDTHS[width]}`}>
            {children}
          </section>
          <div className="flex-[2]" />
        </main>

        <div className="pt-3xl pb-6xl flex w-full justify-center">
          <Chain label={SIGNIN_TEXT.chainLabel} stops={SIGNIN_TEXT.chain} />
        </div>
      </div>
    </div>
  )
}

/**
 * 产品标识，每张门禁页都有。页头是公司的，访客输入产品域名进来，得有一处告诉他到的是哪个产品。
 * 标识与产品名同一行；高度由标识撑住。
 */
function ProductIdentity({ name }: { readonly name: string }) {
  return (
    <div className="gap-md flex items-center">
      {/* 取自 lib/brand-assets，从不写字面路径。 */}
      <img src={PRODUCT_MARK_SRC} alt="" aria-hidden className="h-14 w-auto sm:h-16" />
      <p className="text-title-xl sm:text-heading-2">{name}</p>
    </div>
  )
}

/**
 * 产品的信息带：走过的流程，展示而不是描述，四张门禁页共用的下段。
 *
 * 有序列表，因为顺序就是内容；箭头是装饰，不进阅读顺序。比中段宽：英文比中文长，760px 会换行，
 * 1040px 在 1920 宽下让英文保持一行（用浏览器量，不看图）。
 */
function Chain({ label, stops }: { readonly label: string; readonly stops: readonly string[] }) {
  return (
    <nav aria-label={label} className="w-full max-w-[1040px]">
      <div className="gap-md flex items-center">
        <span className="border-primary/15 h-px flex-1 border-t" />
        <span className="text-overline text-muted-foreground">{label}</span>
        <span className="border-primary/15 h-px flex-1 border-t" />
      </div>

      <ol className="gap-x-xs gap-y-sm pt-xl flex flex-wrap items-center justify-center">
        {stops.map((stop, i) => (
          <li key={stop} className="gap-x-xs flex items-center">
            <span className="text-label-sm border-primary/15 bg-card/70 px-sm py-2xs rounded-full border">
              {stop}
            </span>
            {/* 挂在自己这一站之后，而不是下一站之前：手机上换行时一行不会以一个指向虚空的箭头开头。 */}
            {i < stops.length - 1 && (
              <Icon name="chevron-right" size={12} aria-hidden className="text-muted-foreground/50" />
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

/**
 * 门禁页的底色：顶部一道辉光，底部一条波浪（占视口 55%）。
 *
 * 权宜之计：DS 还没有氛围背景元件，有了就删掉这里改用它（yucer 登记为 TD-005）。
 * 颜色全部取自 DS token（--primary / --background），本地不定义任何色值，所以跟着品牌与亮暗主题走。
 * 纯装饰：aria-hidden、不接收指针事件。
 */
function Ambience() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {/* 一道来自顶边之上的光。 */}
      <div className="absolute inset-0 bg-[radial-gradient(120%_78%_at_50%_-12%,color-mix(in_srgb,var(--primary)_17%,transparent),transparent_62%)]" />

      {/* 一条波浪，渐变跟着曲线走，不是跟着外框走。
          单条纵向渐变只在外框顶端全透明，而曲线低的那一侧起点已在渐变中段，边缘出现可见的硬边。
          所以同一条路径画 16 遍、每遍下移 14 个单位、每遍几乎透明：紧贴曲线的像素只被一遍覆盖，
          深处被 16 遍覆盖——离曲线的深度决定浓淡，高处低处每一段边缘都从全透明开始。
          preserveAspectRatio="none"：这是一条带，不是一幅图，任何宽度都要碰到两边。 */}
      <svg
        className="absolute inset-x-0 bottom-0 h-[55%] w-full"
        viewBox="0 0 1440 400"
        preserveAspectRatio="none"
      >
        <defs>
          {/* 斜坡上的一个波：一谷一峰，左低右高。880 处的衔接按构造光滑：出点控制点 (1120 64)
              是入点控制点 (620 236) 关于该点的镜像。 */}
          <path
            id="gate-wave"
            d="M0 244 C 330 300, 620 236, 880 150 C 1120 64, 1240 104, 1440 46 L1440 400 L0 400 Z"
          />
        </defs>

        <g fill="var(--primary)" fillOpacity="0.016">
          {Array.from({ length: 16 }, (_, i) => (
            <use key={i} href="#gate-wave" y={i * 14} />
          ))}
        </g>
      </svg>
    </div>
  )
}
