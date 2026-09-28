import { useNavigate } from 'react-router'
import { CheckIcon, HomeIcon, UsersIcon } from './icons'
import logoMark from '../../assets/logo-mark.svg'

export type ReceptionSidebarActiveItem = 'dashboard' | 'visits' | 'my-actions'

interface ReceptionSidebarProps {
  activeItem: ReceptionSidebarActiveItem
}

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'visits', label: 'Visits', icon: UsersIcon },
  { key: 'my-actions', label: 'My actions', icon: CheckIcon },
] as const satisfies ReadonlyArray<{
  key: ReceptionSidebarActiveItem
  label: string
  icon: unknown
}>

const RECEPTION_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: ReceptionSidebarActiveItem]> = [
  ['/reception/dashboard', 'dashboard'],
  ['/staff/dashboard', 'visits'],
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

  const handleActivate = (key: ReceptionSidebarActiveItem) => {
    if (key === 'dashboard') navigate('/reception/dashboard')
    if (key === 'visits') navigate('/staff/dashboard')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <aside className="flex w-[280px] shrink-0 flex-col gap-4 self-stretch bg-primary p-6">
      <button
        type="button"
        onClick={() => navigate('/reception/dashboard')}
        className="flex items-center gap-2 pb-4 text-left"
      >
        <img src={logoMark} alt="" className="size-8 shrink-0" />
        <span className="font-display text-[22px] font-extrabold whitespace-nowrap text-white">VisitorPass</span>
      </button>

      <nav className="flex flex-1 flex-col gap-1.5">
        {NAV_ITEMS.map(({ key, label, icon: ItemIcon }) => (
          <button
            key={key}
            type="button"
            onClick={() => handleActivate(key)}
            className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left font-body text-sm font-semibold whitespace-nowrap ${
              activeItem === key ? 'bg-admin-accent text-white' : 'text-text-faint hover:bg-white/5'
            }`}
          >
            <ItemIcon className="size-[18px] shrink-0" />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
