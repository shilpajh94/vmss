import { useRef } from 'react'
import { useNavigate } from 'react-router'
import {
  BuildingIcon,
  CalendarCheckIcon,
  CalendarIcon,
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
} from './icons'
import { useNavDrawer } from '../context/nav-drawer-context'
import { usePermissions } from '../context/current-user-context'
import { PAGE_PERMISSIONS } from '../route-permissions'
import { useSidebarCollapse } from '../context/sidebar-collapse-context'
import { SidebarFrame } from './sidebar/SidebarFrame'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarNavItem } from './sidebar/SidebarNavItem'
import { useScrollActivity } from '../hooks/use-scroll-activity'

const BUILD_LABEL = [__APP_VERSION__ ? `v${__APP_VERSION__}` : '', __BUILD_SHA__].filter(Boolean).join(' · ')

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
  | 'calendar'
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
  ['/admin/calendar', 'calendar'],
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

// The permission each entry's page requires (App.tsx's `requires`); an entry
// the user can't open is hidden, and a section left empty with it.
const NAV_ITEM_PERMISSIONS: Record<AdminSidebarActiveItem, string> = {
  dashboard: PAGE_PERMISSIONS.adminDashboard,
  'organisation-configs': PAGE_PERMISSIONS.organisationConfigs,
  branches: PAGE_PERMISSIONS.branches,
  departments: PAGE_PERMISSIONS.departments,
  buildings: PAGE_PERMISSIONS.buildings,
  floors: PAGE_PERMISSIONS.floors,
  'reception-desks': PAGE_PERMISSIONS.receptionDesks,
  'security-gates': PAGE_PERMISSIONS.securityGates,
  kiosks: PAGE_PERMISSIONS.kiosks,
  'host-employees': PAGE_PERMISSIONS.hostEmployees,
  'visitor-categories': PAGE_PERMISSIONS.visitorCategories,
  workflows: PAGE_PERMISSIONS.workflows,
  invitations: PAGE_PERMISSIONS.adminInvitations,
  calendar: PAGE_PERMISSIONS.calendar,
  roles: PAGE_PERMISSIONS.roles,
  'form-builder': PAGE_PERMISSIONS.formBuilder,
  'audit-trail': PAGE_PERMISSIONS.auditTrail,
}

// Ordered by how often admins use each page, daily operations first and
// one-time organisation setup last, in labelled sections (app-shell
// "Sidebar menus are ordered by how often they are used").
const NAV_SECTIONS = [
  {
    label: 'Operations',
    items: [
      { key: 'dashboard', label: 'Dashboard', icon: HomeIcon },
      { key: 'invitations', label: 'Invitations', icon: CalendarCheckIcon },
      { key: 'calendar', label: 'Calendar', icon: CalendarIcon },
      { key: 'audit-trail', label: 'Audit Trail', icon: ClockIcon },
    ],
  },
  {
    label: 'People & Access',
    items: [
      { key: 'host-employees', label: 'Employees', icon: UserCheckIcon },
      { key: 'roles', label: 'Roles & Permissions', icon: ShieldIcon },
    ],
  },
  {
    label: 'Visitor Setup',
    items: [
      { key: 'visitor-categories', label: 'Visitor Categories', icon: TagIcon },
      { key: 'workflows', label: 'Workflows', icon: ListChecksIcon },
      { key: 'form-builder', label: 'Form Builder', icon: PencilIcon },
    ],
  },
  {
    label: 'Organisation',
    items: [
      { key: 'branches', label: 'Branches', icon: GitBranchIcon },
      { key: 'buildings', label: 'Buildings', icon: BuildingIcon },
      { key: 'floors', label: 'Floors', icon: LayersIcon },
      { key: 'departments', label: 'Departments', icon: UsersIcon },
      { key: 'reception-desks', label: 'Reception Desks', icon: MonitorIcon },
      { key: 'security-gates', label: 'Security Gates', icon: ShieldIcon },
      { key: 'kiosks', label: 'Kiosks', icon: MonitorIcon },
      { key: 'organisation-configs', label: 'Organisation Configs', icon: SettingsIcon },
    ],
  },
] as const satisfies ReadonlyArray<{
  label: string
  items: ReadonlyArray<{ key: AdminSidebarActiveItem; label: string; icon: unknown }>
}>

type NavItem = (typeof NAV_SECTIONS)[number]['items'][number]

const NAV_ITEMS: readonly NavItem[] = NAV_SECTIONS.flatMap((section): readonly NavItem[] => section.items)

// The nav label for the current admin route, e.g. "Branches" — what the
// phone top bar shows as the page name when the page has no breadcrumb.
export function adminNavLabelFor(pathname: string): string {
  const activeItem = resolveAdminActiveItem(pathname)
  return NAV_ITEMS.find((item) => item.key === activeItem)?.label ?? 'Dashboard'
}

export function AdminSidebar({ activeItem }: AdminSidebarProps) {
  const navigate = useNavigate()
  const navRef = useRef<HTMLElement>(null)
  useScrollActivity(navRef)
  const { closeNav } = useNavDrawer()
  const { isCollapsed } = useSidebarCollapse()
  const { can } = usePermissions()
  const sections = NAV_SECTIONS.map((section) => ({
    label: section.label,
    items: section.items.filter((item) => can(NAV_ITEM_PERMISSIONS[item.key])),
  })).filter((section) => section.items.length > 0)

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
    if (key === 'calendar') navigate('/admin/calendar')
    if (key === 'roles') navigate('/admin/roles')
    if (key === 'form-builder') navigate('/admin/form-builder')
    if (key === 'audit-trail') navigate('/admin/audit-trail')
  }

  return (
    <SidebarFrame expandedWidthClassName="w-[min(280px,85vw)] lg:w-[280px]" gapClassName="gap-4">
      <SidebarHeader
        className="pb-4"
        onHome={() => {
          closeNav()
          navigate('/admin/dashboard')
        }}
      />

      <nav ref={navRef} className="sidebar-nav-scroll flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
        {sections.map((section, index) => (
          // The group's aria-label names the section for screen readers, so
          // the visible label is aria-hidden; on the icon rail a thin divider
          // stands in for it.
          <div key={section.label} role="group" aria-label={section.label} className="flex flex-col gap-1.5">
            {isCollapsed ? (
              index > 0 ? <div aria-hidden className="mx-2 my-2 h-px bg-sidebar-line" /> : null
            ) : (
              <p
                aria-hidden
                className={`px-3 pb-1 font-body text-[11px] font-semibold uppercase tracking-wide text-sidebar-muted ${index > 0 ? 'pt-3' : ''}`}
              >
                {section.label}
              </p>
            )}
            {section.items.map(({ key, label, icon }) => (
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
          </div>
        ))}
      </nav>

      {/* The deployed build, injected at build time (app-shell "The sidebar
          footer shows the real build identifier") — hidden on the rail. */}
      {BUILD_LABEL && !isCollapsed ? (
        <div className="flex shrink-0 items-center border-t border-sidebar-line pt-4">
          <span className="font-body text-xs font-medium text-sidebar-muted" title="Deployed build">
            {BUILD_LABEL}
          </span>
        </div>
      ) : null}
    </SidebarFrame>
  )
}
