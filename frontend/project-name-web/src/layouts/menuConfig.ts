// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
export type PortalKind = 'planner' | 'admin'

export interface MenuItem {
  name: string
  path: string
  meta: {
    icon?: string
    title: string
    description?: string
    isHide: boolean
    isFull: boolean
    isExternal?: boolean
    externalUrl?: string
  }
  children?: MenuItem[]
}

export const plannerMenuList: MenuItem[] = [
  {
    name: 'Writing',
    path: '/planner/writing',
    meta: {
      icon: 'pen-line',
      title: '标书写作',
      description: '按评分点编制',
      isHide: false,
      isFull: false,
    },
  },
  {
    name: 'BidAssets',
    path: '/planner/assets',
    meta: {
      icon: 'library',
      title: '素材管理',
      description: '范本、大纲与图库',
      isHide: false,
      isFull: false,
    },
  },
  {
    name: 'Bids',
    path: '/planner/bids',
    meta: {
      icon: 'files',
      title: '我的标书',
      description: '进度与成果',
      isHide: false,
      isFull: false,
    },
  },
  {
    name: 'Account',
    path: '/planner/account',
    meta: {
      icon: 'circle-user-round',
      title: '个人资料',
      description: '平台账号身份与控制台资料入口',
      isHide: false,
      isFull: false,
    },
  },
]

export const adminMenuList: MenuItem[] = [
  {
    name: 'AuditLogs',
    path: '/console/audit-logs',
    meta: {
      icon: 'scroll-text',
      title: '审计日志',
      description: '操作筛选与追溯',
      isHide: false,
      isFull: false,
    },
  },
  {
    name: 'Diagnostics',
    path: '/console/diagnostics',
    meta: {
      icon: 'plugs-connected',
      title: '系统验证',
      description: '与平台和 Atlas 的对接是否健康',
      isHide: false,
      isFull: false,
    },
  },
]

export const getPortalKind = (pathname: string): PortalKind =>
  pathname.startsWith('/console') ? 'admin' : 'planner'

export const getMenuListByPortal = (portal: PortalKind) =>
  portal === 'admin' ? adminMenuList : plannerMenuList
