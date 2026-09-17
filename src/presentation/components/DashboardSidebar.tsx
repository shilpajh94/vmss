import { useNavigate } from 'react-router'
import { CheckIcon, HelpCircleIcon, UsersIcon } from './icons'
import logoMark from '../../assets/logo-mark.svg'

export type DashboardSidebarActiveItem = 'all-visitors' | 'my-actions'

interface DashboardSidebarProps {
  activeItem: DashboardSidebarActiveItem
}

const NAV_ITEMS = [
  { key: 'all-visitors', label: 'All visitors', icon: UsersIcon },
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

export function DashboardSidebar({ activeItem }: DashboardSidebarProps) {
  const navigate = useNavigate()

  const handleActivate = (key: DashboardSidebarActiveItem) => {
    if (key === 'all-visitors') navigate('/staff/dashboard')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <aside className="flex w-[260px] shrink-0 flex-col gap-8 self-stretch bg-primary p-6">
      <button
        type="button"
        onClick={() => navigate('/staff/dashboard')}
        className="flex shrink-0 items-center gap-3 text-left"
      >
        <img src={logoMark} alt="" className="size-8 shrink-0" />
        <span className="font-display text-xl font-extrabold whitespace-nowrap text-white">VisitorPass</span>
      </button>

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
