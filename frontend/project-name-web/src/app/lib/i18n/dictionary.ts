// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-15
import { DEFAULT_LOCALE, type Locale } from '@vxture/shared'

import * as zh from '../messages'
import { en } from '../messages.en'

// 词典：一个形状，每种语言一份（参照 vx-agent-yucer app/(app)/lib/i18n/dictionary.ts）。
//
// 形状由 zh-CN 推出，从不手写：messages.ts 的常量是 `as const`，字面量类型收窄到中文原文，
// 英文译文按定义不是那个字面量，所以把字面量放宽回基础类型，函数签名保持不变——
// 译者不能悄悄改掉一个函数的参数个数。

type Widen<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends (...args: infer A) => infer R
        ? (...args: A) => R
        : { -readonly [K in keyof T]: Widen<T[K]> }

/** 每种语言必须满足的形状。 */
export type Dictionary = Widen<typeof zh>

const DICTIONARIES: Record<Locale, Dictionary> = {
  'zh-CN': zh as Dictionary,
  'en-US': en,
}

/** 没有的语言退回平台默认值而不是抛错：缺一种语言是渲染中文的理由，不是什么都不渲染的理由。 */
export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale] ?? DICTIONARIES[DEFAULT_LOCALE]
}
