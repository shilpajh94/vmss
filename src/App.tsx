import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, Route, RouterProvider, Routes } from 'react-router'
import { LoadingState } from './presentation/components/ui/LoadingState'
import { AppDependenciesProvider } from './presentation/context/app-dependencies-context'
import { ToastProvider } from './presentation/components/toast/toast-context'
import { PushNotificationsProvider } from './presentation/components/push-notifications/PushNotificationsProvider'
import { SessionExpiryListener } from './presentation/components/session/SessionExpiryListener'
import { PublicLayout } from './presentation/components/PublicLayout'
import { AdminLayout } from './presentation/components/AdminLayout'
import { StaffLayout } from './presentation/components/StaffLayout'
import { NotificationCenterProvider } from './presentation/context/notification-center-context'
import { ThemeModeProvider } from './presentation/context/theme-mode-context'
import { UnsavedChangesProvider } from './presentation/context/unsaved-changes-context'
import { VisitorPortalLandingPage } from './presentation/pages/visitor-portal-landing/visitor-portal-landing'
import { VisitorRequestPage } from './presentation/pages/visitor-request/visitor-request'
import { VisitorTrackPage } from './presentation/pages/visitor-track/visitor-track'
import { StaffLoginPage } from './presentation/pages/staff-login/staff-login'
import { StaffSsoLoginPage } from './presentation/pages/staff-sso-login/staff-sso-login'
import { StaffInvitationsPage } from './presentation/pages/staff-invitations/staff-invitations'
import { StaffVisitorRegistrationPage } from './presentation/pages/staff-visitor-registration/staff-visitor-registration'
import { AdminOrganisationConfigsPage } from './presentation/pages/admin-organisation-configs/admin-organisation-configs'
import { AdminBranchesPage } from './presentation/pages/admin-branches/admin-branches'
import { AdminBranchCreatePage } from './presentation/pages/admin-branches/admin-branch-create'
import { AdminDepartmentsPage } from './presentation/pages/admin-departments/admin-departments'
import { AdminDepartmentFormPage } from './presentation/pages/admin-departments/admin-department-form'
import { AdminBuildingsPage } from './presentation/pages/admin-buildings/admin-buildings'
import { AdminBuildingFormPage } from './presentation/pages/admin-buildings/admin-building-form'
import { AdminFloorsPage } from './presentation/pages/admin-floors/admin-floors'
import { AdminFloorFormPage } from './presentation/pages/admin-floors/admin-floor-form'
import { AdminHostEmployeesPage } from './presentation/pages/admin-host-employees/admin-host-employees'
import { AdminHostEmployeeFormPage } from './presentation/pages/admin-host-employees/admin-host-employee-form'
import { AdminReceptionDesksPage } from './presentation/pages/admin-reception-desks/admin-reception-desks'
import { AdminSecurityGatesPage } from './presentation/pages/admin-security-gates/admin-security-gates'
import { AdminKiosksPage } from './presentation/pages/admin-kiosks/admin-kiosks'
import { AdminKioskFormPage } from './presentation/pages/admin-kiosks/admin-kiosk-form'
import { AdminVisitorCategoriesPage } from './presentation/pages/admin-visitor-categories/admin-visitor-categories'
import { AdminVisitorCategoryFormPage } from './presentation/pages/admin-visitor-categories/admin-visitor-category-form'
import { AdminWorkflowsPage } from './presentation/pages/admin-workflows/admin-workflows'
import { AdminWorkflowFormPage } from './presentation/pages/admin-workflows/admin-workflow-form'
import { AdminInvitationsPage } from './presentation/pages/admin-invitations/admin-invitations'
import { AdminRolesPage } from './presentation/pages/admin-roles/admin-roles'
import { AdminRolePermissionsFormPage } from './presentation/pages/admin-roles/admin-role-permissions-form'
import { AdminRoleCreateFormPage } from './presentation/pages/admin-roles/admin-role-create-form'
import { AdminFormBuilderPage } from './presentation/pages/admin-form-builder/admin-form-builder'
import { AdminFormBuilderStepEditorPage } from './presentation/pages/admin-form-builder/admin-form-builder-step-editor'
import { AdminAuditTrailPage } from './presentation/pages/admin-audit-trail/admin-audit-trail'

// The dashboards are the only pages that render charts; loading them lazily
// keeps the chart library out of the public portal and login bundles
// (live-dashboards-and-analytics design.md W5).
const AdminDashboardPage = lazy(() =>
  import('./presentation/pages/admin-dashboard/admin-dashboard').then((module) => ({ default: module.AdminDashboardPage })),
)
const ReceptionDashboardPage = lazy(() =>
  import('./presentation/pages/reception-dashboard/reception-dashboard').then((module) => ({ default: module.ReceptionDashboardPage })),
)
const StaffDashboardPage = lazy(() =>
  import('./presentation/pages/staff-dashboard/staff-dashboard').then((module) => ({ default: module.StaffDashboardPage })),
)
// add-staff-calendar: one page for both portals (design.md W5).
const CalendarPage = lazy(() => import('./presentation/pages/calendar/calendar-page').then((module) => ({ default: module.CalendarPage })))

function LazyPage({ children, label = 'Loading dashboard…' }: { children: ReactNode; label?: string }) {
  return <Suspense fallback={<LoadingState label={label} className="flex-1" />}>{children}</Suspense>
}

function RootLayout() {
  return (
    <ThemeModeProvider>
      <ToastProvider>
        <AppDependenciesProvider>
          <UnsavedChangesProvider>
            <NotificationCenterProvider>
              <SessionExpiryListener />
              <PushNotificationsProvider>
                <Routes>
                  <Route element={<PublicLayout />}>
                    <Route path="/" element={<VisitorPortalLandingPage />} />
                    <Route path="/visitor/request" element={<VisitorRequestPage />} />
                    <Route path="/visitor/track" element={<VisitorTrackPage />} />
                    <Route path="/admin/login" element={<StaffLoginPage />} />
                    <Route path="/staff/login" element={<StaffSsoLoginPage />} />
                  </Route>

                  <Route element={<AdminLayout />}>
                    <Route
                      path="/admin/dashboard"
                      element={
                        <LazyPage>
                          <AdminDashboardPage />
                        </LazyPage>
                      }
                    />
                    <Route path="/admin/organisation-configs" element={<AdminOrganisationConfigsPage />} />
                    <Route path="/admin/branches" element={<AdminBranchesPage />} />
                    <Route path="/admin/branches/new" element={<AdminBranchCreatePage />} />
                    <Route path="/admin/departments" element={<AdminDepartmentsPage />} />
                    <Route path="/admin/departments/new" element={<AdminDepartmentFormPage />} />
                    <Route path="/admin/departments/:id/edit" element={<AdminDepartmentFormPage />} />
                    <Route path="/admin/buildings" element={<AdminBuildingsPage />} />
                    <Route path="/admin/buildings/new" element={<AdminBuildingFormPage />} />
                    <Route path="/admin/buildings/:id/edit" element={<AdminBuildingFormPage />} />
                    <Route path="/admin/floors" element={<AdminFloorsPage />} />
                    <Route path="/admin/floors/new" element={<AdminFloorFormPage />} />
                    <Route path="/admin/floors/:id/edit" element={<AdminFloorFormPage />} />
                    <Route path="/admin/host-employees" element={<AdminHostEmployeesPage />} />
                    <Route path="/admin/host-employees/new" element={<AdminHostEmployeeFormPage />} />
                    <Route path="/admin/host-employees/:id/edit" element={<AdminHostEmployeeFormPage />} />
                    <Route path="/admin/reception-desks" element={<AdminReceptionDesksPage />} />
                    <Route path="/admin/reception-desks/*" element={<Navigate to="/admin/reception-desks" replace />} />
                    <Route path="/admin/security-gates" element={<AdminSecurityGatesPage />} />
                    <Route path="/admin/security-gates/*" element={<Navigate to="/admin/security-gates" replace />} />
                    <Route path="/admin/kiosks" element={<AdminKiosksPage />} />
                    <Route path="/admin/kiosks/new" element={<AdminKioskFormPage />} />
                    <Route path="/admin/kiosks/:id/edit" element={<AdminKioskFormPage />} />
                    <Route path="/admin/visitor-categories" element={<AdminVisitorCategoriesPage />} />
                    <Route path="/admin/visitor-categories/new" element={<AdminVisitorCategoryFormPage />} />
                    <Route path="/admin/visitor-categories/:id/edit" element={<AdminVisitorCategoryFormPage />} />
                    <Route path="/admin/workflows" element={<AdminWorkflowsPage />} />
                    <Route path="/admin/workflows/new" element={<AdminWorkflowFormPage />} />
                    <Route path="/admin/workflows/:visitorCategoryId/edit" element={<AdminWorkflowFormPage />} />
                    <Route path="/admin/invitations" element={<AdminInvitationsPage />} />
                    <Route
                      path="/admin/calendar"
                      element={
                        <LazyPage label="Loading calendar…">
                          <CalendarPage loginPath="/admin/login" boardBasePath="/admin/invitations" />
                        </LazyPage>
                      }
                    />
                    <Route path="/admin/roles" element={<AdminRolesPage />} />
                    <Route path="/admin/roles/new" element={<AdminRoleCreateFormPage />} />
                    <Route path="/admin/roles/:id/edit" element={<AdminRolePermissionsFormPage />} />
                    <Route path="/admin/form-builder" element={<AdminFormBuilderPage />} />
                    <Route path="/admin/form-builder/steps/:stepId" element={<AdminFormBuilderStepEditorPage />} />
                    <Route path="/admin/audit-trail" element={<AdminAuditTrailPage />} />
                  </Route>

                  <Route element={<StaffLayout />}>
                    <Route
                      path="/staff/dashboard"
                      element={
                        <LazyPage>
                          <StaffDashboardPage />
                        </LazyPage>
                      }
                    />
                    {/* Under the staff layout so reception shares its top bar,
                        refresh control and current-user context; the page
                        keeps its own Reception-role guard. */}
                    <Route
                      path="/reception/dashboard"
                      element={
                        <LazyPage>
                          <ReceptionDashboardPage />
                        </LazyPage>
                      }
                    />
                    <Route path="/staff/invitations" element={<StaffInvitationsPage />} />
                    <Route
                      path="/staff/calendar"
                      element={
                        <LazyPage label="Loading calendar…">
                          <CalendarPage loginPath="/staff/login" boardBasePath="/staff/invitations" />
                        </LazyPage>
                      }
                    />
                    <Route path="/staff/visitors/new" element={<StaffVisitorRegistrationPage />} />
                  </Route>
                </Routes>
              </PushNotificationsProvider>
            </NotificationCenterProvider>
          </UnsavedChangesProvider>
        </AppDependenciesProvider>
      </ToastProvider>
    </ThemeModeProvider>
  )
}

// A data router, so forms can block navigation while they hold unsaved
// input (`useBlocker`, design D-W6). The route tree itself stays in
// `RootLayout`'s <Routes>, under one splat route.
const router = createBrowserRouter([{ path: '*', element: <RootLayout /> }])

function App() {
  return <RouterProvider router={router} />
}

export default App
