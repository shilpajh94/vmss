import { useNavigate } from 'react-router'
import {
  BuildingIcon,
  CalendarCheckIcon,
  ClockIcon,
  GitBranchIcon,
  HomeIcon,
  LayersIcon,
  ListChecksIcon,
  MonitorIcon,
  PencilIcon,
  SettingsIcon,
  ShieldIcon,
  TagIcon,
  UserCheckIcon,
  UsersIcon,
  XIcon,
} from './icons'
import { BrandLogo } from './BrandLogo'
import { useNavDrawer } from '../context/nav-drawer-context'

export type AdminSidebarActiveItem =
  | 'dashboard'
  | 'organisation-configs'
  | 'branches'
  | 'departments'
  | 'buildings'
  | 'floors'
  | 'reception-desks'
  | 'security-gates'
  | 'kiosks'
  | 'host-employees'
  | 'visitor-categories'
  | 'workflows'
  | 'invitations'
  | 'roles'
  | 'form-builder'
  | 'audit-trail'

interface AdminSidebarProps {
  activeItem: AdminSidebarActiveItem
}

const ADMIN_ROUTE_ACTIVE_ITEMS: ReadonlyArray<readonly [prefix: string, item: AdminSidebarActiveItem]> = [
  ['/admin/dashboard', 'dashboard'],
  ['/admin/organisation-configs', 'organisation-configs'],
  ['/admin/branches', 'branches'],
  ['/admin/departments', 'departments'],
  ['/admin/buildings', 'buildings'],
  ['/admin/floors', 'floors'],
  ['/admin/reception-desks', 'reception-desks'],
  ['/admin/security-gates', 'security-gates'],
  ['/admin/kiosks', 'kiosks'],
  ['/admin/host-employees', 'host-employees'],
  ['/admin/visitor-categories', 'visitor-categories'],
  ['/admin/workflows', 'workflows'],
  ['/admin/invitations', 'invitations'],
  ['/admin/roles', 'roles'],
  ['/admin/form-builder', 'form-builder'],
  ['/admin/audit-trail', 'audit-trail'],
]

// Derives which sidebar entry highlights from the current URL, so the active
// item can never drift out of sync with the route table the way a hardcoded
// per-page prop could.
export function resolveAdminActiveItem(pathname: string): AdminSidebarActiveItem {
  return ADMIN_ROUTE_ACTIVE_ITEMS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'dashboard'
}

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
  { key: 'organisation-configs', label: 'Organisation Configs', icon: SettingsIcon },
  { key: 'branches', label: 'Branches', icon: GitBranchIcon },
  { key: 'departments', label: 'Departments', icon: UsersIcon },
  { key: 'buildings', label: 'Buildings', icon: BuildingIcon },
  { key: 'floors', label: 'Floors', icon: LayersIcon },
  { key: 'reception-desks', label: 'Reception Desks', icon: MonitorIcon },
  { key: 'security-gates', label: 'Security Gates', icon: ShieldIcon },
  { key: 'kiosks', label: 'Kiosks', icon: MonitorIcon },
  { key: 'host-employees', label: 'Employees', icon: UserCheckIcon },
  { key: 'visitor-categories', label: 'Visitor Categories', icon: TagIcon },
  { key: 'workflows', label: 'Workflows', icon: ListChecksIcon },
  { key: 'invitations', label: 'Invitations', icon: CalendarCheckIcon },
  { key: 'roles', label: 'Roles & Permissions', icon: ShieldIcon },
  { key: 'form-builder', label: 'Form Builder', icon: PencilIcon },
  { key: 'audit-trail', label: 'Audit Trail', icon: ClockIcon },
] as const satisfies ReadonlyArray<{ key: AdminSidebarActiveItem; label: string; icon: unknown }>

// The nav label for the current admin route, e.g. "Branches" — what the
// phone top bar shows as the page name when the page has no breadcrumb.
export function adminNavLabelFor(pathname: string): string {
  const activeItem = resolveAdminActiveItem(pathname)
  return NAV_ITEMS.find((item) => item.key === activeItem)?.label ?? 'Dashboard'
}

export function AdminSidebar({ activeItem }: AdminSidebarProps) {
  const navigate = useNavigate()
  const { closeNav } = useNavDrawer()

  const handleActivate = (key: AdminSidebarActiveItem) => {
    closeNav()
    if (key === 'dashboard') navigate('/admin/dashboard')
    if (key === 'organisation-configs') navigate('/admin/organisation-configs')
    if (key === 'branches') navigate('/admin/branches')
    if (key === 'departments') navigate('/admin/departments')
    if (key === 'buildings') navigate('/admin/buildings')
    if (key === 'floors') navigate('/admin/floors')
    if (key === 'host-employees') navigate('/admin/host-employees')
    if (key === 'reception-desks') navigate('/admin/reception-desks')
    if (key === 'security-gates') navigate('/admin/security-gates')
    if (key === 'kiosks') navigate('/admin/kiosks')
    if (key === 'visitor-categories') navigate('/admin/visitor-categories')
    if (key === 'workflows') navigate('/admin/workflows')
    if (key === 'invitations') navigate('/admin/invitations')
    if (key === 'roles') navigate('/admin/roles')
    if (key === 'form-builder') navigate('/admin/form-builder')
    if (key === 'audit-trail') navigate('/admin/audit-trail')
  }

  return (
    <aside className="flex h-full w-[min(280px,85vw)] shrink-0 lg:h-auto lg:w-[280px] flex-col gap-4 self-stretch bg-primary p-6">
      <div className="flex shrink-0 items-center justify-between gap-2 pb-4">
        <button
          type="button"
          onClick={() => {
            closeNav()
            navigate('/admin/dashboard')
          }}
          aria-label="Visimio home"
          className="flex shrink-0 items-center gap-2 text-left"
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

      <div className="flex shrink-0 items-center gap-2 border-t border-[#334155] pt-4">
        <span className="size-2 rounded-full bg-success" />
        <span className="font-body text-xs font-medium text-text-faint">v1.2 Active</span>
      </div>
    </aside>
  )
}
