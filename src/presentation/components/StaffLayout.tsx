import { Outlet, useLocation } from 'react-router'
import { DashboardSidebar, resolveStaffActiveItem, staffNavLabelFor } from './DashboardSidebar'
import { ReceptionSidebar, resolveReceptionActiveItem } from './ReceptionSidebar'
import { AppShell } from './AppShell'
import { AppTopBar } from './AppTopBar'
import { RouteTransition } from './RouteTransition'
import { SignInRedirect } from './session/RouteGuards'
import { SessionGateContent } from './session/SessionGateContent'
import { useStaffSession } from './session/use-staff-session'
import { PageHeaderProvider, usePageHeaderContext } from '../context/page-header-context'
import { RefreshProvider } from '../context/refresh-context'
import { CurrentUserProvider } from '../context/current-user-context'
import { useApplyTheme } from '../context/theme-mode-context'

// Persists the sidebar and top bar across every /staff/* route so navigating
// between staff pages only swaps the content inside <Outlet /> instead of
// unmounting the whole page tree (see persistent-nav-shell's proposal.md).
// Mirrors AdminLayout so the staff and admin chrome stay the same, including
// its session check (design D-W3); any signed-in user may enter, and each
// route's `requires` is checked in App.tsx.
function StaffLayoutContent() {
  useApplyTheme()
  const location = useLocation()
  const { header } = usePageHeaderContext()
  const { session, retry } = useStaffSession()
  const currentUser = session.status === 'ready' ? session.user : undefined

  if (session.status === 'signed-out') return <SignInRedirect loginPath="/staff/login" />

  const sidebar = currentUser?.isReception ? (
    <ReceptionSidebar activeItem={resolveReceptionActiveItem(location.pathname)} />
  ) : (
    <DashboardSidebar activeItem={resolveStaffActiveItem(location.pathname)} />
  )

  return (
    <CurrentUserProvider user={currentUser}>
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
        <SessionGateContent session={session} onRetry={retry}>
          <RouteTransition withEndGap>
            <Outlet />
          </RouteTransition>
        </SessionGateContent>
      </AppShell>
    </CurrentUserProvider>
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
