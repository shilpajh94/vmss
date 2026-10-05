import { useNavigate } from 'react-router'
import { CheckIcon, HomeIcon, UsersIcon, XIcon } from './icons'
import { BrandLogo } from './BrandLogo'
import { useNavDrawer } from '../context/nav-drawer-context'

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
  const { closeNav } = useNavDrawer()

  const handleActivate = (key: ReceptionSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/reception/dashboard')
    if (key === 'visits') navigate('/staff/dashboard')
    if (key === 'my-actions') navigate('/staff/visitors/new')
  }

  return (
    <aside className="flex h-full w-[min(280px,85vw)] shrink-0 lg:h-auto lg:w-[280px] flex-col gap-4 self-stretch bg-primary p-6">
      <div className="flex shrink-0 items-center justify-between gap-2 pb-4">
        <button
          type="button"
          onClick={() => {
            closeNav()
            navigate('/reception/dashboard')
          }}
          aria-label="Visimio home"
          className="flex items-center gap-2 text-left"
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

      <nav className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
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
