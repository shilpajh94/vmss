import { Outlet, useLocation } from 'react-router'
import { AdminSidebar, adminNavLabelFor, resolveAdminActiveItem } from './AdminSidebar'
import { AppTopBar } from './AppTopBar'
import { AppShell } from './AppShell'
import { RouteTransition } from './RouteTransition'
import { NotPermittedRedirect, SignInRedirect } from './session/RouteGuards'
import { SessionGateContent } from './session/SessionGateContent'
import { useStaffSession } from './session/use-staff-session'
import { PageHeaderProvider, usePageHeaderContext } from '../context/page-header-context'
import { RefreshProvider } from '../context/refresh-context'
import { CurrentUserProvider } from '../context/current-user-context'
import { useApplyTheme } from '../context/theme-mode-context'
import { landingPathFor } from '../utils/landing-path'
import { ADMIN_AREA_PERMISSIONS, permissionsFor } from '../utils/permissions'

// Persists the sidebar and top bar across every /admin/* route so navigating
// between admin pages only swaps the content inside <Outlet /> instead of
// unmounting the whole page tree (see persistent-nav-shell's proposal.md).
//
// It is also the admin area's one session check (design D-W3): a token, then
// the user, then an admin-management permission, before any page renders.
// Each route's own `requires` is checked by `RequirePermission` in App.tsx.
function AdminLayoutContent() {
  useApplyTheme()
  const location = useLocation()
  const { header } = usePageHeaderContext()
  const { session, retry } = useStaffSession()
  const currentUser = session.status === 'ready' ? session.user : undefined

  if (session.status === 'signed-out') return <SignInRedirect loginPath="/admin/login" />
  if (currentUser && !permissionsFor(currentUser).canAny(ADMIN_AREA_PERMISSIONS)) {
    return <NotPermittedRedirect to={landingPathFor(currentUser)} />
  }

  return (
    <CurrentUserProvider user={currentUser}>
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
        <SessionGateContent session={session} onRetry={retry}>
          <RouteTransition withEndGap>
            <Outlet />
          </RouteTransition>
        </SessionGateContent>
      </AppShell>
    </CurrentUserProvider>
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
