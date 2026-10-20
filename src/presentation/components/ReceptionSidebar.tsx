import { useNavigate } from 'react-router'
import { CalendarIcon, CheckIcon, HomeIcon, UsersIcon } from './icons'
import { useNavDrawer } from '../context/nav-drawer-context'
import { SidebarFrame } from './sidebar/SidebarFrame'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarNavItem } from './sidebar/SidebarNavItem'

export type ReceptionSidebarActiveItem = 'dashboard' | 'visits' | 'calendar' | 'my-actions'

interface ReceptionSidebarProps {
  activeItem: ReceptionSidebarActiveItem
}

// Most-used first: registering a visitor is the desk's and hosts' most
// frequent task (app-shell "Sidebar menus are ordered by how often they are used").
const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'my-actions', label: 'My actions', icon: CheckIcon },
  { key: 'visits', label: 'Invitations', icon: UsersIcon },
  { key: 'calendar', label: 'Calendar', icon: CalendarIcon },
] as const satisfies ReadonlyArray<{
  key: ReceptionSidebarActiveItem
  label: string
  icon: unknown
}>

const RECEPTION_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: ReceptionSidebarActiveItem]> = [
  ['/reception/dashboard', 'dashboard'],
  ['/staff/invitations', 'visits'],
  ['/staff/calendar', 'calendar'],
  ['/staff/visitors/new', 'my-actions'],
]

// Derives which sidebar entry highlights from the current URL, so the active
// item can never drift out of sync with the route table the way a hardcoded
// per-page prop could - mirrors `DashboardSidebar.resolveStaffActiveItem`.
export function resolveReceptionActiveItem(pathname: string): ReceptionSidebarActiveItem {
  return RECEPTION_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'dashboard'
}

export function ReceptionSidebar({ activeItem }: ReceptionSidebarProps) {
  const navigate = useNavigate()
  const { closeNav } = useNavDrawer()

  const handleActivate = (key: ReceptionSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/reception/dashboard')
    if (key === 'visits') navigate('/staff/invitations')
    if (key === 'calendar') navigate('/staff/calendar')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <SidebarFrame expandedWidthClassName="w-[min(280px,85vw)] lg:w-[280px]" gapClassName="gap-4">
      <SidebarHeader
        className="pb-4"
        onHome={() => {
          closeNav()
          navigate('/reception/dashboard')
        }}
      />

      <nav className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
        {NAV_ITEMS.map(({ key, label, icon }) => (
          <SidebarNavItem
            key={key}
            icon={icon}
            label={label}
            isActive={activeItem === key}
            onActivate={() => handleActivate(key)}
            activeClassName="bg-sidebar-accent text-white"
            inactiveClassName="text-sidebar-muted hover:bg-white/5"
          />
        ))}
      </nav>
    </SidebarFrame>
  )
}
