import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { AdminSidebar, adminNavLabelFor, resolveAdminActiveItem } from './AdminSidebar'
import { AppTopBar } from './AppTopBar'
import { AppShell } from './AppShell'
import { RouteTransition } from './RouteTransition'
import { PageHeaderProvider, usePageHeaderContext } from '../context/page-header-context'
import { RefreshProvider } from '../context/refresh-context'
import { CurrentUserProvider } from '../context/current-user-context'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

// Persists the sidebar and top bar across every /admin/* route so navigating
// between admin pages only swaps the content inside <Outlet /> instead of
// unmounting the whole page tree (see persistent-nav-shell's proposal.md).
function AdminLayoutContent() {
  const location = useLocation()
  const { header } = usePageHeaderContext()
  const { getCurrentStaffUserUseCase } = useAppDependencies()
  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)

  useEffect(() => {
    getCurrentStaffUserUseCase
      .execute()
      .then(setCurrentUser)
      .catch((error: unknown) => {
        console.error('Failed to load current admin user', error)
      })
  }, [getCurrentStaffUserUseCase])

  return (
    <AppShell
      sidebar={<AdminSidebar activeItem={resolveAdminActiveItem(location.pathname)} />}
      topBar={
        <AppTopBar
          title="Organization Admin"
          description={header.description}
          breadcrumb={header.breadcrumb}
          currentUser={currentUser}
          navLabelFor={adminNavLabelFor}
          loginPath="/admin/login"
        />
      }
    >
      <CurrentUserProvider user={currentUser}>
        <RouteTransition>
          <Outlet />
        </RouteTransition>
      </CurrentUserProvider>
    </AppShell>
  )
}

export function AdminLayout() {
  return (
    <PageHeaderProvider>
      <RefreshProvider>
        <AdminLayoutContent />
      </RefreshProvider>
    </PageHeaderProvider>
  )
}
