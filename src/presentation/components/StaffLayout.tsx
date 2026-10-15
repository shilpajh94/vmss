import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { DashboardSidebar, resolveStaffActiveItem, staffNavLabelFor } from './DashboardSidebar'
import { ReceptionSidebar, resolveReceptionActiveItem } from './ReceptionSidebar'
import { AppShell } from './AppShell'
import { AppTopBar } from './AppTopBar'
import { RouteTransition } from './RouteTransition'
import { PageHeaderProvider, usePageHeaderContext } from '../context/page-header-context'
import { RefreshProvider } from '../context/refresh-context'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

// Persists the sidebar and top bar across every /staff/* route so navigating
// between staff pages only swaps the content inside <Outlet /> instead of
// unmounting the whole page tree (see persistent-nav-shell's proposal.md).
// Mirrors AdminLayout so the staff and admin chrome stay the same.
function StaffLayoutContent() {
  const location = useLocation()
  const { header } = usePageHeaderContext()
  const { getCurrentStaffUserUseCase } = useAppDependencies()
  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)

  useEffect(() => {
    getCurrentStaffUserUseCase
      .execute()
      .then(setCurrentUser)
      .catch((error: unknown) => {
        console.error('Failed to load current staff user', error)
      })
  }, [getCurrentStaffUserUseCase])

  const sidebar = currentUser?.isReception ? (
    <ReceptionSidebar activeItem={resolveReceptionActiveItem(location.pathname)} />
  ) : (
    <DashboardSidebar activeItem={resolveStaffActiveItem(location.pathname)} />
  )

  return (
    <AppShell
      sidebar={sidebar}
      topBar={
        <AppTopBar
          title={currentUser?.isReception ? 'Reception Desk' : 'Staff Workspace'}
          description={header.description}
          currentUser={currentUser}
          navLabelFor={staffNavLabelFor}
          loginPath="/staff/login"
        />
      }
    >
      <RouteTransition>
        <Outlet />
      </RouteTransition>
    </AppShell>
  )
}

export function StaffLayout() {
  return (
    <PageHeaderProvider>
      <RefreshProvider>
        <StaffLayoutContent />
      </RefreshProvider>
    </PageHeaderProvider>
  )
}
