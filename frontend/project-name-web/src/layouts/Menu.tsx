// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-07-28
import { forwardRef, useMemo } from 'react'
import { Link, useLocation } from 'react-router'

import {
  Button,
  cn,
  Icon,
  type IconName,
  ShellSidebarNav,
} from '@vxture/design-system'

import { useGlobalStore } from '@/stores/global'

import { getMenuListByPortal, getPortalKind, type MenuItem } from './menuConfig'

type LayoutMenuProps = {
  variant?: 'sidebar' | 'mobile'
}

const iconMap: Record<string, IconName> = {
  'circle-user-round': 'user-circle',
  'file-check-2': 'seal-check',
  'folder-kanban': 'kanban',
  'folder-open': 'folder-open',
  files: 'file',
  images: 'image',
  library: 'building-library',
  'layout-dashboard': 'squares-four',
  'pen-line': 'edit',
  'plugs-connected': 'plugs-connected',
  'shield-check': 'shield-check',
  'scroll-text': 'clipboard',
  'sliders-horizontal': 'faders',
  users: 'users',
}

const getSelectedMenu = (items: MenuItem[], pathname: string) =>
  items.find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`))?.path

export default function LayoutMenu({ variant = 'sidebar' }: LayoutMenuProps) {
  const location = useLocation()
  const { themeConfig, setThemeConfig } = useGlobalStore()
  const portal = getPortalKind(location.pathname)
  const menuList = useMemo(
    () => getMenuListByPortal(portal),
    [portal]
  )
  const selectedKey = useMemo(
    () => getSelectedMenu(menuList, location.pathname) ?? menuList[0]?.path,
    [location.pathname, menuList]
  )

  if (variant === 'sidebar') {
    return (
      <ShellSidebarNav
        domainName={portal === 'admin' ? '系统管理' : '标书编制'}
        sections={[
          {
            title: portal === 'admin' ? '管理' : '工作区',
            brandPosition: 'none',
            items: menuList.map((item) => ({
              href: item.path,
              label: item.meta.title,
              icon: iconMap[item.meta.icon ?? ''] ?? 'placeholder',
            })),
          },
        ]}
        collapsed={themeConfig.isCollapsed}
        onToggleCollapsed={() =>
          setThemeConfig({ isCollapsed: !themeConfig.isCollapsed })
        }
        isActive={(href) =>
          location.pathname === href || location.pathname.startsWith(`${href}/`)
        }
        storageKeyPrefix="tenderagent-sidebar"
        linkComponent={RouterNavLink}
        labels={{
          expandNav: '展开导航',
          collapseNav: '收起导航',
          expandAllGroups: '展开全部分组',
          collapseAllGroups: '收起全部分组',
        }}
      />
    )
  }

  return (
    <nav
      aria-label={portal === 'admin' ? '管理导航' : '编制导航'}
      className={cn(
        'grid w-full gap-2xs px-2xs py-xs',
        portal === 'admin' ? 'grid-cols-2' : 'grid-cols-4'
      )}
    >
      {menuList.map((item) => {
        const icon = item.meta.icon ? iconMap[item.meta.icon] : null
        const isSelected = selectedKey === item.path

        return (
          <Button
            key={item.path}
            asChild
            variant={isSelected ? 'secondary' : 'ghost'}
            size="sm"
            className={cn(
              'min-w-0 justify-center gap-2xs',
              isSelected && 'text-primary-text'
            )}
          >
            <Link to={item.path}>
              {icon ? <Icon name={icon} size="sm" /> : null}
              <span className="min-w-0 truncate">{item.meta.title}</span>
            </Link>
          </Button>
        )
      })}
    </nav>
  )
}

const RouterNavLink = forwardRef<
  HTMLAnchorElement,
  React.ComponentPropsWithoutRef<'a'>
>(function RouterNavLink({ href = '/', ...props }, ref) {
  return <Link ref={ref} to={href} {...props} />
})
