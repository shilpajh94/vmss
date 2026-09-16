import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { DashboardSidebar, resolveStaffActiveItem } from './DashboardSidebar'
import { ReceptionSidebar, resolveReceptionActiveItem } from './ReceptionSidebar'
import { AppShell } from './AppShell'
import { RouteTransition } from './RouteTransition'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

// Persists the sidebar across every /staff/* route so navigating between
// staff pages only swaps the content inside <Outlet /> instead of unmounting
// the whole page tree (see persistent-nav-shell's proposal.md). Unlike
// AdminLayout, there is no shared top bar to hoist here — each staff page
// keeps rendering its own distinct header as page content.
export function StaffLayout() {
  const location = useLocation()
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
    <AppShell sidebar={sidebar}>
      <RouteTransition>
        <Outlet />
      </RouteTransition>
    </AppShell>
  )
}
