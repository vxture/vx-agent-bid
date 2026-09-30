// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import type { Locale } from '@vxture/shared'

import { getDictionary } from './dictionary'
import { resolveLocale } from './locale'
import { MessagesContext } from './use-messages'
import { writeLocale } from './write-locale'

// 词典，给组件用（参照 vx-agent-yucer app/(app)/lib/i18n/provider.tsx）。
//
// 与 yucer 的差别：yucer 切换语言后让服务端重新渲染（router.refresh），本产品没有服务端渲染，
// 所以语言放在这里的状态里，切换即重渲染，同时写 cookie 并更新 <html lang>——
// 否则英文页面对读屏软件和浏览器翻译都自称中文。

export function MessagesProvider({
  initialLocale,
  children,
}: {
  /** 预览页与测试用；不传时按 cookie、浏览器语言、平台默认值解析。 */
  readonly initialLocale?: Locale
  readonly children: ReactNode
}) {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale ?? resolveLocale())

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    writeLocale(next)
    setLocaleState(next)
  }, [])

  const value = useMemo(() => ({ t: getDictionary(locale), locale, setLocale }), [locale, setLocale])
  return <MessagesContext.Provider value={value}>{children}</MessagesContext.Provider>
}
