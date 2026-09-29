// @vitest-environment happy-dom
// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { render, screen } from '@testing-library/react'

import { useAuthStore } from '@/stores/auth'
import type { CurrentUser } from '@/types/auth'

import PortalRedirect from './index'

const user = (admin: boolean): CurrentUser => ({
  id: 'usr-1',
  username: 'usr-1',
  displayName: '编制员',
  roleCode: admin ? 'ADMIN' : 'PLANNER',
  avatarUrl: null,
  orgName: null,
  workspaceName: null,
  email: null,
  phone: null,
  admin,
  consoleProfileUrl: null,
})

function Where() {
  return <p>{`at ${useLocation().pathname}`}</p>
}

describe('登录后的落点', () => {
  afterEach(() => useAuthStore.setState({ user: null }))

  it.each([
    ['编制人员', false],
    ['管理员', true],
  ])('%s落在标书编制首页，而不是管理面', async (_, admin) => {
    useAuthStore.setState({ user: user(admin) })

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PortalRedirect />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('at /planner/writing')).toBeTruthy()
  })
})
