// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-27
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'

import type { ShellSearchGroup } from '@vxture/design-system'
import {
  ShellBrand,
  ShellFullscreenToggle,
  ShellHeader,
  ShellIconButton,
  ShellIconGroup,
  ShellPreferencePanel,
  ShellSearchBox,
  ShellThemeToggle,
  ShellUserMenu,
  useTheme,
} from '@vxture/design-system'

import { authApi } from '@/api/modules/auth'
import { BRAND_MARK_SRC } from '@/app/lib/brand-assets'
import { accessState, subscriptionBadgeLabel } from '@/features/entitlement/access'
import { useEntitlementQuery } from '@/features/entitlement/queries'
import { useAuthStore } from '@/stores/auth'
import { useGlobalStore } from '@/stores/global'
import { platformAvatarSrc } from '@/utils/avatar'

import { logoutAndLeave } from './logout'
import type { MenuItem } from './menuConfig'
import { getMenuListByPortal } from './menuConfig'

function usePortalSearch(menuItems: readonly MenuItem[]) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLocaleLowerCase('zh-CN')

  const groups = useMemo<ShellSearchGroup[]>(() => {
    const matchingItems = menuItems.filter((item) => {
      const searchableText = `${item.meta.title} ${item.meta.description ?? ''}`
      return searchableText.toLocaleLowerCase('zh-CN').includes(normalizedQuery)
    })

    return [
      {
        key: 'portal-navigation',
        heading: '功能导航',
        items: matchingItems.map((item) => ({
          key: item.name,
          label: item.meta.title,
          description: item.meta.description,
          icon: 'arrow-right',
          onSelect: () => navigate(item.path),
        })),
      },
    ]
  }, [menuItems, navigate, normalizedQuery])

  return { groups, query, setQuery }
}

function HeaderTools() {
  const isCollapsed = useGlobalStore((state) => state.themeConfig.isCollapsed)
  const setThemeConfig = useGlobalStore((state) => state.setThemeConfig)
  const { setTheme, theme } = useTheme()

  return (
    <ShellIconGroup label="页面工具">
      <ShellIconButton
        icon="sidebar"
        label={isCollapsed ? '展开侧栏' : '收起侧栏'}
        active={isCollapsed}
        className="hidden lg:inline-flex"
        onClick={() => setThemeConfig({ isCollapsed: !isCollapsed })}
      />
      <ShellThemeToggle
        currentTheme={theme}
        lightLabel="切换到亮色模式"
        darkLabel="切换到暗色模式"
        onThemeChange={setTheme}
      />
      <ShellFullscreenToggle
        targetId="tenderagent-app-shell"
        enterLabel="进入全屏"
        exitLabel="退出全屏"
        getTargetElement={() => document.getElementById('tenderagent-app-shell')}
      />
    </ShellIconGroup>
  )
}

function logout(clearAuth: () => void) {
  return logoutAndLeave({
    logout: authApi.logout,
    clearAuth,
    go: (url) => {
      window.location.href = url
    },
  })
}

function AccountPanel() {
  const user = useAuthStore((state) => state.user)
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const { density, fontSize, mode, setDensity, setFontSize, setMode } = useTheme()
  const entitlement = useEntitlementQuery()
  const displayName = user?.displayName || user?.username || '当前用户'
  const roleLabel = user?.admin ? '管理员' : '标书编制人员'
  // 订阅徽标与闸门读同一份权益缓存；还没取到时不显示，免得先闪一下「暂不可知」。
  const badges = [{ key: 'role', label: roleLabel }]
  if (!entitlement.isPending) {
    const access = entitlement.isError ? ({ kind: 'unavailable' } as const) : accessState(entitlement.data)
    badges.push({ key: 'subscription', label: subscriptionBadgeLabel(access) })
  }

  return (
    <ShellUserMenu
      user={{
        displayName,
        uniqueLine: user?.username,
        // IdP 的 picture 是外部绝对地址，直接渲染；不走本站的受保护读取。
        avatarSrc: platformAvatarSrc(user?.avatarUrl) ?? '',
        avatarAlt: displayName,
        avatarFallback: displayName.slice(0, 1),
        meta: `${roleLabel}账户`,
        statusTag: { label: '已登录', verified: true },
        badges,
      }}
      openLabel="打开账号菜单"
      settings={
        <ShellPreferencePanel
          locale="zh-CN"
          localeOptions={[{ locale: 'zh-CN', nativeName: '简体中文' }]}
          theme={mode}
          density={density}
          fontSize={fontSize}
          labels={{
            title: '显示偏好',
            locale: '界面语言',
            theme: '主题',
            density: '界面密度',
            fontSize: '字号',
            themeOptions: { system: '系统', light: '亮色', dark: '暗色' },
            densityOptions: { compact: '紧凑', default: '标准', comfortable: '宽松' },
            fontSizeOptions: { small: '小', default: '标准', large: '大' },
          }}
          onLocaleChange={() => undefined}
          onThemeChange={setMode}
          onDensityChange={setDensity}
          onFontSizeChange={setFontSize}
        />
      }
      // 管理员与编制人员同一个入口：账号归平台，本产品不再有本地账号管理页。
      // 登录一律落在编制首页，管理员从这里进管理面（审计日志、系统验证）。
      links={[
        { key: 'account', label: '个人资料', href: '/planner/account', icon: 'user-circle' },
        ...(user?.admin
          ? [{ key: 'console', label: '系统管理', href: '/console/audit-logs', icon: 'shield-check' as const }]
          : []),
      ]}
      actions={[
        {
          key: 'logout',
          label: '退出登录',
          icon: 'sign-out',
          danger: true,
          onClick: () => logout(clearAuth),
        },
      ]}
    />
  )
}

export default function LayoutHeader() {
  const user = useAuthStore((state) => state.user)
  // 管理员两边都用：登录落在编制首页，搜索框同样要能直达管理面。
  const isAdmin = Boolean(user?.admin)
  const menuItems = useMemo(
    () =>
      isAdmin
        ? [...getMenuListByPortal('planner'), ...getMenuListByPortal('admin')]
        : getMenuListByPortal('planner'),
    [isAdmin]
  )
  const search = usePortalSearch(menuItems)

  return (
    <ShellHeader
      height="md"
      leading={
        <ShellBrand
          href="/"
          logoSrc={BRAND_MARK_SRC}
          logoAlt=""
          label="TenderAgent"
          tag="智能标书编制"
          className="[&_.vx-brand-local-name]:hidden xl:[&_.vx-brand-local-name]:inline-flex"
          labelClassName="hidden sm:inline"
        />
      }
      center={
        <div className="w-full max-w-panel-sm">
          <ShellSearchBox
            query={search.query}
            onQueryChange={search.setQuery}
            groups={search.groups}
            labels={{
              placeholder: '搜索功能',
              empty: '没有匹配的功能',
              resultsLabel: '功能搜索结果',
            }}
          />
        </div>
      }
      trailing={
        <>
          <HeaderTools />
          <AccountPanel />
        </>
      }
    />
  )
}
