// @vitest-environment happy-dom
// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { GateProviders } from '@/test/gate-providers'
import type { PlatformCheck, PlatformProbe } from '@/types/admin'

import DiagnosticsPage from './DiagnosticsPage'

const api = vi.hoisted(() => ({
  platformCheck: vi.fn(),
  probeAtlas: vi.fn(),
  probeUsageReplay: vi.fn(),
  listAuditLogs: vi.fn(),
}))
vi.mock('@/api/modules/admin', () => ({ adminApi: api }))

const probe = (overrides: Partial<PlatformProbe> = {}): PlatformProbe => ({
  configured: true,
  ok: true,
  detail: 'ok',
  ...overrides,
})

const check = (): PlatformCheck => ({
  time: '2026-09-29T16:00:00',
  c1: probe({ detail: '发现文档可达' }),
  tokenMint: probe(),
  c2: probe({ ok: false, detail: '换票被平台 D2 覆盖门拒绝（invalid_target）' }),
  c3Up: probe({ configured: false, ok: false, detail: 'PLATFORM_API_URL 未配置' }),
  c3Down: probe(),
  atlas: probe({ detail: '本产品可见 7 个模型' }),
  usageReplay: probe({ ok: false, detail: '只读探测不跑这一项' }),
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <GateProviders>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </GateProviders>
  )
  return render(<DiagnosticsPage />, { wrapper })
}

describe('系统验证', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.platformCheck.mockResolvedValue(check())
  })

  it('三态分开显示：未配置不是异常', async () => {
    renderPage()

    expect(await screen.findByText('本产品可见 7 个模型')).toBeTruthy()
    expect(screen.getByText(/D2 覆盖门/)).toBeTruthy()
    expect(screen.getAllByText('未配置')).toHaveLength(1)
    expect(screen.getAllByText('异常')).toHaveLength(1)
  })

  it('会花钱的探测要经过确认，点一下按钮不花钱', async () => {
    api.probeAtlas.mockResolvedValue({
      ok: false,
      detail: '1/2 条路由走通',
      items: [
        probe({ detail: 'chat/fast：模型 m-fast 应答' }),
        probe({ ok: false, detail: 'chat/reasoning：AI_ATLAS_NOT_ENTITLED' }),
      ],
    })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: '运行 Atlas 探测' }))
    expect(api.probeAtlas).not.toHaveBeenCalled()

    await user.click(await screen.findByRole('button', { name: '确认运行' }))

    await waitFor(() => expect(api.probeAtlas).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('1/2 条路由走通')).toBeTruthy()
    expect(screen.getByText('chat/reasoning：AI_ATLAS_NOT_ENTITLED')).toBeTruthy()
    expect(api.probeUsageReplay).not.toHaveBeenCalled()
  })

  it('取消确认不花钱', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: '运行重放校验' }))
    await user.click(await screen.findByRole('button', { name: '取消' }))

    expect(api.probeUsageReplay).not.toHaveBeenCalled()
  })
})
