import { useNavigate } from 'react-router'
import { CalendarIcon, CheckIcon, HomeIcon, UsersIcon } from './icons'
import { useNavDrawer } from '../context/nav-drawer-context'
import { SidebarFrame } from './sidebar/SidebarFrame'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarNavItem } from './sidebar/SidebarNavItem'

export type DashboardSidebarActiveItem = 'dashboard' | 'all-visitors' | 'calendar' | 'my-actions'

interface DashboardSidebarProps {
  activeItem: DashboardSidebarActiveItem
}

// Most-used first: registering a visitor is the desk's and hosts' most
// frequent task (app-shell "Sidebar menus are ordered by how often they are used").
const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'my-actions', label: 'My actions', icon: CheckIcon },
  { key: 'all-visitors', label: 'Invitations', icon: UsersIcon },
  { key: 'calendar', label: 'Calendar', icon: CalendarIcon },
] as const

const STAFF_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: DashboardSidebarActiveItem]> = [
  ['/staff/dashboard', 'dashboard'],
  ['/staff/invitations', 'all-visitors'],
  ['/staff/calendar', 'calendar'],
  ['/staff/visitors/new', 'my-actions'],
]

// Derives which sidebar entry highlights from the current URL, so the active
// item can never drift out of sync with the route table the way a hardcoded
// per-page prop could.
export function resolveStaffActiveItem(pathname: string): DashboardSidebarActiveItem {
  return STAFF_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'dashboard'
}

// The nav label for the current staff route, e.g. "Invitations" — what the
// phone top bar shows as the page name. Both staff sidebars use the same
// labels for the shared /staff/* routes, so this serves Reception users too.
export function staffNavLabelFor(pathname: string): string {
  const activeItem = resolveStaffActiveItem(pathname)
  return NAV_ITEMS.find((item) => item.key === activeItem)?.label ?? 'Dashboard'
}

export function DashboardSidebar({ activeItem }: DashboardSidebarProps) {
  const navigate = useNavigate()
  const { closeNav } = useNavDrawer()

  const handleActivate = (key: DashboardSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/staff/dashboard')
    if (key === 'all-visitors') navigate('/staff/invitations')
    if (key === 'calendar') navigate('/staff/calendar')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <SidebarFrame expandedWidthClassName="w-[min(260px,85vw)] lg:w-[260px]" gapClassName="gap-8">
      <SidebarHeader
        onHome={() => {
          closeNav()
          navigate('/staff/dashboard')
        }}
      />

      <nav className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {NAV_ITEMS.map(({ key, label, icon }) => (
          <SidebarNavItem
            key={key}
            icon={icon}
            label={label}
            isActive={activeItem === key}
            onActivate={() => handleActivate(key)}
            activeClassName="bg-sidebar-raised text-sidebar-text"
            inactiveClassName="text-sidebar-soft hover:bg-sidebar-raised/60"
          />
        ))}
      </nav>

    </SidebarFrame>
  )
}
