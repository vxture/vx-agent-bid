// @vitest-environment happy-dom
// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-30
import { describe, expect, it } from 'vitest'

import { render, screen } from '@testing-library/react'

import type { BidOutlineTask } from '@/types/tender'

import { OutlineWarnings } from './OutlineWarnings'

const task = (overrides: Partial<BidOutlineTask> = {}): BidOutlineTask => ({
  id: 't-1',
  status: 'SUCCEEDED',
  stage: 'COMPLETE',
  progress: 100,
  inputRevision: 1,
  workflowRunId: null,
  errorMessage: null,
  createdAt: '2026-09-30T12:00:00',
  startedAt: null,
  finishedAt: null,
  warnings: [],
  ...overrides,
})

describe('目录提示', () => {
  it('生成成功且有偏差时逐条显示，并说明不影响使用', () => {
    render(
      <OutlineWarnings
        task={task({ warnings: ['二级目录共49个，多于按篇幅估算的上限21个', '三级小节共98个'] })}
      />
    )

    expect(screen.getByText('目录已生成，有 2 条提示供参考')).toBeTruthy()
    expect(screen.getByText('二级目录共49个，多于按篇幅估算的上限21个')).toBeTruthy()
    expect(screen.getByText(/提示不影响使用/)).toBeTruthy()
  })

  it('没有提示、生成中或失败时不显示', () => {
    const { container, rerender } = render(<OutlineWarnings task={task()} />)
    expect(container.textContent).toBe('')

    rerender(<OutlineWarnings task={task({ status: 'RUNNING', warnings: ['x'] })} />)
    expect(container.textContent).toBe('')

    rerender(<OutlineWarnings task={null} />)
    expect(container.textContent).toBe('')
  })
})
