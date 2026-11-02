import { useRef } from 'react'
import { useNavigate } from 'react-router'
import { CalendarIcon, HomeIcon, IdCardIcon, PlusIcon, UsersIcon } from './icons'
import { useNavDrawer } from '../context/nav-drawer-context'
import { usePermissions } from '../context/current-user-context'
import { PAGE_PERMISSIONS } from '../route-permissions'
import { SidebarFrame } from './sidebar/SidebarFrame'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarNavItem } from './sidebar/SidebarNavItem'
import { useScrollActivity } from '../hooks/use-scroll-activity'
import { useBadgePrintFlow } from '../hooks/use-badge-print-flow'

export type ReceptionSidebarActiveItem = 'dashboard' | 'visits' | 'calendar' | 'register-visitor' | 'badge-printing'

interface ReceptionSidebarProps {
  activeItem: ReceptionSidebarActiveItem
}

// Most-used first: registering a visitor is the desk's and hosts' most
// frequent task (app-shell "Sidebar menus are ordered by how often they are used").
const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'register-visitor', label: 'Register Visitor', icon: PlusIcon },
  { key: 'visits', label: 'Invitations', icon: UsersIcon },
  { key: 'calendar', label: 'Calendar', icon: CalendarIcon },
  { key: 'badge-printing', label: 'Badge Printing', icon: IdCardIcon },
] as const satisfies ReadonlyArray<{
  key: ReceptionSidebarActiveItem
  label: string
  icon: unknown
}>

const RECEPTION_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: ReceptionSidebarActiveItem]> = [
  ['/reception/dashboard', 'dashboard'],
  ['/staff/invitations', 'visits'],
  ['/staff/calendar', 'calendar'],
  ['/staff/visitors/new', 'register-visitor'],
  ['/reception/badge-printing', 'badge-printing'],
]

// Entries the user can't open are hidden (app-shell "Admin and Staff Areas
// and Their Actions Are Gated by the Caller's Permissions").
const NAV_ITEM_PERMISSIONS: Partial<Record<ReceptionSidebarActiveItem, string>> = {
  visits: PAGE_PERMISSIONS.staffInvitations,
  calendar: PAGE_PERMISSIONS.calendar,
  'register-visitor': PAGE_PERMISSIONS.registerVisitor,
  'badge-printing': PAGE_PERMISSIONS.badgePrinting,
}

// Derives which sidebar entry highlights from the current URL, so the active
// item can never drift out of sync with the route table the way a hardcoded
// per-page prop could - mirrors `DashboardSidebar.resolveStaffActiveItem`.
export function resolveReceptionActiveItem(pathname: string): ReceptionSidebarActiveItem {
  return RECEPTION_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'dashboard'
}

export function ReceptionSidebar({ activeItem }: ReceptionSidebarProps) {
  const navigate = useNavigate()
  const navRef = useRef<HTMLElement>(null)
  useScrollActivity(navRef)
  const { closeNav } = useNavDrawer()
  const { can } = usePermissions()
  const badgePrintFlow = useBadgePrintFlow()

  const handleActivate = (key: ReceptionSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/reception/dashboard')
    if (key === 'visits') navigate('/staff/invitations')
    if (key === 'calendar') navigate('/staff/calendar')
    if (key === 'register-visitor') navigate('/staff/visitors/new')
    if (key === 'badge-printing') navigate('/reception/badge-printing')
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

      <nav ref={navRef} className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
        {NAV_ITEMS.filter(({ key }) => {
          const requires = NAV_ITEM_PERMISSIONS[key]
          if (key === 'badge-printing' && badgePrintFlow !== 'on') return false
          return !requires || can(requires)
        }).map(({ key, label, icon }) => (
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
