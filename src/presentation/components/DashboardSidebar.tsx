import { useNavigate } from 'react-router'
import { CheckIcon, HelpCircleIcon, HomeIcon, UsersIcon } from './icons'
import { useNavDrawer } from '../context/nav-drawer-context'
import { useSidebarCollapse } from '../context/sidebar-collapse-context'
import { SidebarFrame } from './sidebar/SidebarFrame'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarNavItem, useRailTooltip } from './sidebar/SidebarNavItem'

export type DashboardSidebarActiveItem = 'dashboard' | 'all-visitors' | 'my-actions'

interface DashboardSidebarProps {
  activeItem: DashboardSidebarActiveItem
}

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'all-visitors', label: 'Invitations', icon: UsersIcon },
  { key: 'my-actions', label: 'My actions', icon: CheckIcon },
] as const

const STAFF_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: DashboardSidebarActiveItem]> = [
  ['/staff/dashboard', 'dashboard'],
  ['/staff/invitations', 'all-visitors'],
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
  const { isCollapsed } = useSidebarCollapse()
  const helpTooltip = useRailTooltip('Help & Support', isCollapsed)

  const handleActivate = (key: DashboardSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/staff/dashboard')
    if (key === 'all-visitors') navigate('/staff/invitations')
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
            activeClassName="bg-[#1e293b] text-[#f1f5f9]"
            inactiveClassName="text-[#cbd5e1] hover:bg-[#1e293b]/60"
          />
        ))}
      </nav>

      <div className="flex shrink-0 flex-col gap-4">
        <div className="h-px w-full bg-[#1e293b]" />
        <button
          type="button"
          aria-label={isCollapsed ? 'Help & Support' : undefined}
          {...helpTooltip.handlers}
          className={`flex w-full items-center gap-2 rounded-lg bg-[#1e293b] py-2 text-left ${isCollapsed ? 'justify-center px-0' : 'px-3'}`}
        >
          <HelpCircleIcon className="size-4 shrink-0 text-secondary-accent" />
          {isCollapsed ? null : (
            <span className="font-body text-[13px] font-semibold whitespace-nowrap text-secondary-accent">Help &amp; Support</span>
          )}
        </button>
        {helpTooltip.tooltip}
      </div>
    </SidebarFrame>
  )
}
