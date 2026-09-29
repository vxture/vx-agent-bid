// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router'
import { createBrowserRouter, Navigate } from 'react-router'

import { ShellBootScreen } from '@vxture/design-system'

import { SignIn } from '@/app/components/sign-in'
import { SHELL_TEXT } from '@/app/lib/messages'
import { SubscriptionGate } from '@/features/entitlement/SubscriptionGate'
import { MainLayout } from '@/layouts'
import Forbidden from '@/pages/Forbidden'
import NotFound from '@/pages/NotFound'
import PortalRedirect from '@/pages/PortalRedirect'
import ServerError from '@/pages/ServerError'

import AuthGuard from './AuthGuard'
import RouteErrorPage from './RouteErrorPage'

type PageModule = { default: ComponentType }

// 路由表在模块加载时建好，拿不到语言上下文；启动屏只闪一下，用默认词典的产品名。
const hydrateFallbackElement = (
  <ShellBootScreen label={SHELL_TEXT.brandName} description="正在加载工作台" delayMs={250} />
)

const lazyPage = (loader: () => Promise<PageModule>) => async () => ({
  Component: (await loader()).default,
})

const lazyProtectedPage = (loader: () => Promise<PageModule>) => async () => {
  const Page = (await loader()).default
  return {
    Component: () => (
      <AuthGuard>
        <SubscriptionGate>
          <Page />
        </SubscriptionGate>
      </AuthGuard>
    ),
  }
}

const routes: RouteObject[] = [
  {
    path: '/',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    element: (
      <AuthGuard>
        <MainLayout />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <PortalRedirect /> },
      { path: 'planner', element: <Navigate to="/planner/writing" replace /> },
      {
        path: 'planner/writing',
        lazy: lazyPage(() => import('@/features/tender/WritingMethodPage')),
      },
      {
        path: 'planner/assets',
        lazy: lazyPage(() => import('@/features/tender/TenderAssetsPage')),
      },
      { path: 'planner/bids', lazy: lazyPage(() => import('@/features/tender/BidsPage')) },
      { path: 'planner/account', lazy: lazyPage(() => import('@/pages/PlannerAccount')) },
      { path: 'console', element: <Navigate to="/console/audit-logs" replace /> },
      {
        path: 'console/audit-logs',
        lazy: lazyPage(() => import('@/pages/AdminAuditLogs')),
      },
      {
        path: 'console/diagnostics',
        lazy: lazyPage(() => import('@/pages/AdminDiagnostics')),
      },
      { path: 'admin/*', element: <Navigate to="/console/audit-logs" replace /> },
    ],
  },
  {
    path: '/planner/bids/new/setup',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidSetupPage')),
  },
  {
    path: '/planner/bids/:bidId/setup',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidSetupPage')),
  },
  {
    path: '/planner/bids/:bidId/interpretation',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidInterpretationPage')),
  },
  {
    path: '/planner/bids/:bidId/outline',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidOutlinePage')),
  },
  {
    path: '/planner/bids/:bidId/generating',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidGeneratingPage')),
  },
  {
    path: '/planner/bids/:bidId/content',
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement,
    lazy: lazyProtectedPage(() => import('@/features/tender/BidContentPage')),
  },
  // 旧链接与书签：引导页本身就地渲染在任何没有会话的地址上，这里只为不让 /login 落到 404。
  { path: '/login', element: <SignIn /> },
  // 四张门禁页的预览：示例数据，不需要会话与平台（参照 yucer 的 gate-screens 预览路由）。
  { path: '/gate-screens', lazy: lazyPage(() => import('@/app/demo/gate-screens')) },
  { path: '/403', element: <Forbidden /> },
  { path: '/404', element: <NotFound /> },
  { path: '/500', element: <ServerError /> },
  { path: '*', element: <NotFound /> },
]

const router = createBrowserRouter(routes, { basename: import.meta.env.VITE_BASE_PATH || '/' })

export default router
