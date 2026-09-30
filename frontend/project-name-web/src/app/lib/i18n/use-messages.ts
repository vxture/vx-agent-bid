// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-30
import { createContext, useContext } from 'react'

import type { Locale } from '@vxture/shared'

import type { Dictionary } from './dictionary'

// 词典的上下文与读取它的 hook。与 <MessagesProvider> 分成两个文件：
// 一个文件里同时导出组件和非组件时，Vite 的 Fast Refresh 无法只热替换组件，
// 改一行词典读取逻辑就会整页重载（react-refresh/only-export-components）。

export interface MessagesValue {
  readonly t: Dictionary
  readonly locale: Locale
  readonly setLocale: (next: Locale) => void
}

export const MessagesContext = createContext<MessagesValue | null>(null)

/**
 * 当前词典。在 Provider 外调用直接抛错而不是退回中文：静默退回会让漏挂的 Provider 一直藏着，
 * 直到有人切到英文、发现某一块顽固地停在中文——那是最难报告这个问题的读者。
 */
export function useMessages(): Dictionary {
  return useMessagesValue().t
}

export function useLocale(): Locale {
  return useMessagesValue().locale
}

export function useSetLocale(): (next: Locale) => void {
  return useMessagesValue().setLocale
}

function useMessagesValue(): MessagesValue {
  const value = useContext(MessagesContext)
  if (!value) {
    throw new Error('useMessages must be called inside <MessagesProvider>')
  }
  return value
}
