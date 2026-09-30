// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { type Locale, LOCALE_CONSTANTS } from '@vxture/shared'

// 写下语言选择（参照 vx-agent-yucer app/(app)/lib/i18n/write-locale.ts）。
//
// 用 cookie 而不是 localStorage：同一个键平台各产品共用，服务端渲染的产品要在渲染前读到它，
// localStorage 在那里不存在。在切换那一下就写，而不是卸载时写，标签页被杀掉也不丢。

export function writeLocale(locale: Locale): void {
  // 一年：这是偏好，不是会话事实。SameSite=Lax 让它跟着正常导航带回来；不写死 Secure，
  // 否则 http 的本地开发里永远种不上，也就没人测得到。
  document.cookie = `${LOCALE_CONSTANTS.COOKIE_KEY}=${locale}; path=/; max-age=31536000; samesite=lax`
}
