import { useNavigate } from 'react-router'
import {
  BuildingIcon,
  GitBranchIcon,
  HomeIcon,
  LayersIcon,
  MonitorIcon,
  SettingsIcon,
  ShieldIcon,
  TagIcon,
  UserCheckIcon,
  UsersIcon,
} from './icons'

export type AdminSidebarActiveItem =
  | 'dashboard'
  | 'organisation-configs'
  | 'branches'
  | 'departments'
  | 'buildings'
  | 'floors'
  | 'reception-desks'
  | 'security-gates'
  | 'host-employees'
  | 'visitor-categories'

interface AdminSidebarProps {
  activeItem: AdminSidebarActiveItem
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
  { key: 'host-employees', label: 'Host Employees', icon: UserCheckIcon },
  { key: 'visitor-categories', label: 'Visitor Categories', icon: TagIcon },
] as const satisfies ReadonlyArray<{ key: AdminSidebarActiveItem; label: string; icon: unknown }>

export function AdminSidebar({ activeItem }: AdminSidebarProps) {
  const navigate = useNavigate()

  const handleActivate = (key: AdminSidebarActiveItem) => {
    if (key === 'dashboard') navigate('/admin/dashboard')
    if (key === 'organisation-configs') navigate('/admin/organisation-configs')
    if (key === 'branches') navigate('/admin/branches')
    if (key === 'departments') navigate('/admin/departments')
    if (key === 'buildings') navigate('/admin/buildings')
    if (key === 'floors') navigate('/admin/floors')
    if (key === 'host-employees') navigate('/admin/host-employees')
    if (key === 'reception-desks') navigate('/admin/reception-desks')
    if (key === 'security-gates') navigate('/admin/security-gates')
    if (key === 'visitor-categories') navigate('/admin/visitor-categories')
  }

  return (
    <aside className="flex w-[280px] shrink-0 flex-col gap-4 self-stretch bg-primary p-6">
      <div className="flex items-center gap-2 pb-4">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-admin-accent">
          <ShieldIcon className="size-4 text-white" />
        </span>
        <span className="font-display text-[22px] font-extrabold whitespace-nowrap text-white">VisitorPass</span>
      </div>

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

      <div className="flex items-center gap-2 border-t border-[#334155] pt-4">
        <span className="size-2 rounded-full bg-success" />
        <span className="font-body text-xs font-medium text-text-faint">v1.2 Active</span>
      </div>
    </aside>
  )
}
