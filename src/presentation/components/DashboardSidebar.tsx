import { useNavigate } from 'react-router'
import { CheckIcon, HelpCircleIcon, UsersIcon, XIcon } from './icons'
import { BrandLogo } from './BrandLogo'
import { useNavDrawer } from '../context/nav-drawer-context'

export type DashboardSidebarActiveItem = 'all-visitors' | 'my-actions'

interface DashboardSidebarProps {
  activeItem: DashboardSidebarActiveItem
}

const NAV_ITEMS = [
  { key: 'all-visitors', label: 'Invitations', icon: UsersIcon },
  { key: 'my-actions', label: 'My actions', icon: CheckIcon },
] as const

const STAFF_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: DashboardSidebarActiveItem]> = [
  ['/staff/dashboard', 'all-visitors'],
  ['/staff/visitors/new', 'my-actions'],
]

// Derives which sidebar entry highlights from the current URL, so the active
// item can never drift out of sync with the route table the way a hardcoded
// per-page prop could.
export function resolveStaffActiveItem(pathname: string): DashboardSidebarActiveItem {
  return STAFF_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'all-visitors'
}

// The nav label for the current staff route, e.g. "Invitations" — what the
// phone top bar shows as the page name. Both staff sidebars use the same
// labels for these two routes, so this serves Reception users too.
export function staffNavLabelFor(pathname: string): string {
  const activeItem = resolveStaffActiveItem(pathname)
  return NAV_ITEMS.find((item) => item.key === activeItem)?.label ?? 'Invitations'
}

export function DashboardSidebar({ activeItem }: DashboardSidebarProps) {
  const navigate = useNavigate()
  const { closeNav } = useNavDrawer()

  const handleActivate = (key: DashboardSidebarActiveItem) => {
    closeNav()
    if (key === 'all-visitors') navigate('/staff/dashboard')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <aside className="flex h-full w-[min(260px,85vw)] shrink-0 lg:h-auto lg:w-[260px] flex-col gap-8 self-stretch bg-primary p-6">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => {
            closeNav()
            navigate('/staff/dashboard')
          }}
          aria-label="Visimio home"
          className="flex shrink-0 items-center gap-3 text-left"
        >
          <BrandLogo variant="on-dark" decorative />
        </button>
        <button
          type="button"
          onClick={closeNav}
          aria-label="Close navigation menu"
          className="flex size-10 shrink-0 items-center justify-center rounded-lg text-text-faint hover:bg-white/5 lg:hidden"
        >
          <XIcon className="size-5" />
        </button>
      </div>

      <nav className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {NAV_ITEMS.map(({ key, label, icon: ItemIcon }) => (
          <button
            key={key}
            type="button"
            onClick={() => handleActivate(key)}
            className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left font-body text-sm font-semibold ${
              activeItem === key ? 'bg-[#1e293b] text-[#f1f5f9]' : 'text-[#cbd5e1] hover:bg-[#1e293b]/60'
            }`}
          >
            <ItemIcon className="size-[18px] shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      <div className="flex shrink-0 flex-col gap-4">
        <div className="h-px w-full bg-[#1e293b]" />
        <button type="button" className="flex w-full items-center gap-2 rounded-lg bg-[#1e293b] px-3 py-2 text-left">
          <HelpCircleIcon className="size-4 text-secondary-accent" />
          <span className="font-body text-[13px] font-semibold whitespace-nowrap text-secondary-accent">Help &amp; Support</span>
        </button>
      </div>
    </aside>
  )
}
