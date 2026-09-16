import { Outlet, useLocation } from 'react-router'
import { DashboardSidebar, resolveStaffActiveItem } from './DashboardSidebar'
import { AppShell } from './AppShell'
import { RouteTransition } from './RouteTransition'

// Persists the sidebar across every /staff/* route so navigating between
// staff pages only swaps the content inside <Outlet /> instead of unmounting
// the whole page tree (see persistent-nav-shell's proposal.md). Unlike
// AdminLayout, there is no shared top bar to hoist here — each staff page
// keeps rendering its own distinct header as page content.
export function StaffLayout() {
  const location = useLocation()

  return (
    <AppShell sidebar={<DashboardSidebar activeItem={resolveStaffActiveItem(location.pathname)} />}>
      <RouteTransition>
        <Outlet />
      </RouteTransition>
    </AppShell>
  )
}
