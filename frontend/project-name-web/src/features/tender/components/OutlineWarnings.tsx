// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-30
import { Banner } from '@vxture/design-system'

import type { BidOutlineTask } from '@/types/tender'

/**
 * 目录生成的提示：规模与篇幅估算的偏差、略去的空章节。
 *
 * 警示而不是错误（owner 2026-09-30）：目录照常生成、照常显示、照常可用。数量上的偏差
 * 不再让整份目录失败——那样页面上什么都没有，用户既看不到模型给了什么，也没法判断它好不好。
 * 这里只把偏差说清楚，由用户决定直接用、编辑调整还是重新生成。
 */
export function OutlineWarnings({ task }: { task: BidOutlineTask | null }) {
  if (task?.status !== 'SUCCEEDED' || !task.warnings.length) return null
  return (
    <Banner
      className="mt-lg"
      tone="warning"
      title={`目录已生成，有 ${task.warnings.length} 条提示供参考`}
      description={
        <span className="flex flex-col gap-xs">
          <ul className="list-disc pl-lg">
            {task.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          <span>提示不影响使用：可以直接进入下一步，也可以编辑调整，或重新生成目录。</span>
        </span>
      }
    />
  )
}
