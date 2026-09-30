// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { DEFAULT_LOCALE, type Locale, LOCALE_CONSTANTS, SUPPORTED_LOCALES } from '@vxture/shared'

// 这次访问用哪种语言（参照 vx-agent-yucer app/(app)/lib/i18n/locale.ts）。
//
// 每一样都是平台的：语言联合类型、支持列表、默认值、cookie 键都来自 @vxture/shared，
// 「有哪些语言」不是产品的决定。
//
// 与 yucer 的差别只在落点：yucer 在服务端按请求解析，本产品是单页应用，没有服务端渲染，
// 所以在浏览器里、首次渲染之前解析，并把结果写到 <html lang>——index.html 里那句 lang 只是
// 脚本跑起来之前的占位，不能代表页面实际渲染的语言。

/** 切换器写、这里读的 cookie。名字归平台。 */
export const LOCALE_COOKIE = LOCALE_CONSTANTS.COOKIE_KEY

export function isLocale(value: string | undefined | null): value is Locale {
  return value != null && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

/**
 * 三步：显式选择（cookie）优先于猜测；其次浏览器语言，让第一次访问不至于自动选错；最后是平台默认值。
 *
 * 浏览器语言按主子标签匹配：zh-TW、zh-HK 落到 zh-CN 而不是英文——繁体读者读简体只是不便，
 * 读英文就是被晾着，只有后者算失败。
 */
export function resolveLocale(): Locale {
  const chosen = readCookie(LOCALE_COOKIE)
  if (isLocale(chosen)) return chosen

  const preferred = navigator.languages?.length ? navigator.languages : [navigator.language]
  for (const tag of preferred) {
    if (!tag) continue
    if (isLocale(tag)) return tag
    const primary = tag.split('-')[0]?.toLowerCase()
    const match = SUPPORTED_LOCALES.find((locale) => locale.split('-')[0]?.toLowerCase() === primary)
    if (match) return match
  }

  return DEFAULT_LOCALE
}
