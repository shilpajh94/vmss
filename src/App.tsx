import { Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, Route, RouterProvider, Routes } from 'react-router'
import { LoadingState } from './presentation/components/ui/LoadingState'
import { lazyPage } from './presentation/components/lazy-page'
import { RouteErrorPage } from './presentation/pages/not-found/route-error'
import { AppDependenciesProvider } from './presentation/context/app-dependencies-context'
import { ToastProvider } from './presentation/components/toast/toast-context'
import { PushNotificationsProvider } from './presentation/components/push-notifications/PushNotificationsProvider'
import { SessionExpiryListener } from './presentation/components/session/SessionExpiryListener'
import { PublicLayout } from './presentation/components/PublicLayout'
import { NotificationCenterProvider } from './presentation/context/notification-center-context'
import { ThemeModeProvider } from './presentation/context/theme-mode-context'
import { UnsavedChangesProvider } from './presentation/context/unsaved-changes-context'
import { RequirePermission } from './presentation/components/session/RouteGuards'
import { PAGE_PERMISSIONS } from './presentation/route-permissions'
import { VisitorPortalLandingPage } from './presentation/pages/visitor-portal-landing/visitor-portal-landing'
import { NotFoundPage } from './presentation/pages/not-found/not-found'

// Every page but the visitor landing page (and the not-found page) is its
// own chunk, loaded the first time its route opens, so a visitor on a phone
// downloads only the public pages (design D13). The layouts' Suspense shows
// their loading state meanwhile.
const VisitorRequestPage = lazyPage(() => import('./presentation/pages/visitor-request/visitor-request'), 'VisitorRequestPage')
const VisitorTrackPage = lazyPage(() => import('./presentation/pages/visitor-track/visitor-track'), 'VisitorTrackPage')
const StaffLoginPage = lazyPage(() => import('./presentation/pages/staff-login/staff-login'), 'StaffLoginPage')
const StaffSsoLoginPage = lazyPage(() => import('./presentation/pages/staff-sso-login/staff-sso-login'), 'StaffSsoLoginPage')
const StaffInvitationsPage = lazyPage(() => import('./presentation/pages/staff-invitations/staff-invitations'), 'StaffInvitationsPage')
const StaffVisitorRegistrationPage = lazyPage(() => import('./presentation/pages/staff-visitor-registration/staff-visitor-registration'), 'StaffVisitorRegistrationPage')
const AdminOrganisationConfigsPage = lazyPage(() => import('./presentation/pages/admin-organisation-configs/admin-organisation-configs'), 'AdminOrganisationConfigsPage')
const AdminBranchesPage = lazyPage(() => import('./presentation/pages/admin-branches/admin-branches'), 'AdminBranchesPage')
const AdminBranchCreatePage = lazyPage(() => import('./presentation/pages/admin-branches/admin-branch-create'), 'AdminBranchCreatePage')
const AdminDepartmentsPage = lazyPage(() => import('./presentation/pages/admin-departments/admin-departments'), 'AdminDepartmentsPage')
const AdminDepartmentFormPage = lazyPage(() => import('./presentation/pages/admin-departments/admin-department-form'), 'AdminDepartmentFormPage')
const AdminBuildingsPage = lazyPage(() => import('./presentation/pages/admin-buildings/admin-buildings'), 'AdminBuildingsPage')
const AdminBuildingFormPage = lazyPage(() => import('./presentation/pages/admin-buildings/admin-building-form'), 'AdminBuildingFormPage')
const AdminFloorsPage = lazyPage(() => import('./presentation/pages/admin-floors/admin-floors'), 'AdminFloorsPage')
const AdminFloorFormPage = lazyPage(() => import('./presentation/pages/admin-floors/admin-floor-form'), 'AdminFloorFormPage')
const AdminHostEmployeesPage = lazyPage(() => import('./presentation/pages/admin-host-employees/admin-host-employees'), 'AdminHostEmployeesPage')
const AdminHostEmployeeFormPage = lazyPage(() => import('./presentation/pages/admin-host-employees/admin-host-employee-form'), 'AdminHostEmployeeFormPage')
const AdminReceptionDesksPage = lazyPage(() => import('./presentation/pages/admin-reception-desks/admin-reception-desks'), 'AdminReceptionDesksPage')
const AdminSecurityGatesPage = lazyPage(() => import('./presentation/pages/admin-security-gates/admin-security-gates'), 'AdminSecurityGatesPage')
const AdminKiosksPage = lazyPage(() => import('./presentation/pages/admin-kiosks/admin-kiosks'), 'AdminKiosksPage')
const AdminKioskFormPage = lazyPage(() => import('./presentation/pages/admin-kiosks/admin-kiosk-form'), 'AdminKioskFormPage')
const AdminVisitorCategoriesPage = lazyPage(() => import('./presentation/pages/admin-visitor-categories/admin-visitor-categories'), 'AdminVisitorCategoriesPage')
const AdminVisitorCategoryFormPage = lazyPage(() => import('./presentation/pages/admin-visitor-categories/admin-visitor-category-form'), 'AdminVisitorCategoryFormPage')
const AdminWorkflowsPage = lazyPage(() => import('./presentation/pages/admin-workflows/admin-workflows'), 'AdminWorkflowsPage')
const AdminWorkflowFormPage = lazyPage(() => import('./presentation/pages/admin-workflows/admin-workflow-form'), 'AdminWorkflowFormPage')
const AdminInvitationsPage = lazyPage(() => import('./presentation/pages/admin-invitations/admin-invitations'), 'AdminInvitationsPage')
const AdminRolesPage = lazyPage(() => import('./presentation/pages/admin-roles/admin-roles'), 'AdminRolesPage')
const AdminRolePermissionsFormPage = lazyPage(() => import('./presentation/pages/admin-roles/admin-role-permissions-form'), 'AdminRolePermissionsFormPage')
const AdminRoleCreateFormPage = lazyPage(() => import('./presentation/pages/admin-roles/admin-role-create-form'), 'AdminRoleCreateFormPage')
const AdminFormBuilderPage = lazyPage(() => import('./presentation/pages/admin-form-builder/admin-form-builder'), 'AdminFormBuilderPage')
const AdminFormBuilderStepEditorPage = lazyPage(() => import('./presentation/pages/admin-form-builder/admin-form-builder-step-editor'), 'AdminFormBuilderStepEditorPage')
const AdminAuditTrailPage = lazyPage(() => import('./presentation/pages/admin-audit-trail/admin-audit-trail'), 'AdminAuditTrailPage')
// The staff shells (sidebar, top bar, notification bell) are only for
// signed-in users, so they are chunks too.
const AdminLayout = lazyPage(() => import('./presentation/components/AdminLayout'), 'AdminLayout')
const StaffLayout = lazyPage(() => import('./presentation/components/StaffLayout'), 'StaffLayout')
const AdminDashboardPage = lazyPage(() => import('./presentation/pages/admin-dashboard/admin-dashboard'), 'AdminDashboardPage')
const ReceptionDashboardPage = lazyPage(() => import('./presentation/pages/reception-dashboard/reception-dashboard'), 'ReceptionDashboardPage')
const ReceptionBadgePrintingPage = lazyPage(() => import('./presentation/pages/reception-badge-printing/reception-badge-printing'), 'ReceptionBadgePrintingPage')
const BadgeScanPage = lazyPage(() => import('./presentation/pages/badge-scan/badge-scan'), 'BadgeScanPage')
const StaffDashboardPage = lazyPage(() => import('./presentation/pages/staff-dashboard/staff-dashboard'), 'StaffDashboardPage')
// add-staff-calendar: one page for both portals (design.md W5).
const CalendarPage = lazyPage(() => import('./presentation/pages/calendar/calendar-page'), 'CalendarPage')

interface PageRoute {
  path: string
  element: ReactNode
  // The permission the page needs (design D-W1); checked by
  // `RequirePermission` once the layout has the signed-in user.
  requires?: string
}

const ADMIN_ROUTES: PageRoute[] = [
  {
    path: '/admin/dashboard',
    requires: PAGE_PERMISSIONS.adminDashboard,
    element: <AdminDashboardPage />,
  },
  { path: '/admin/organisation-configs', requires: PAGE_PERMISSIONS.organisationConfigs, element: <AdminOrganisationConfigsPage /> },
  { path: '/admin/branches', requires: PAGE_PERMISSIONS.branches, element: <AdminBranchesPage /> },
  { path: '/admin/branches/new', requires: PAGE_PERMISSIONS.branches, element: <AdminBranchCreatePage /> },
  { path: '/admin/departments', requires: PAGE_PERMISSIONS.departments, element: <AdminDepartmentsPage /> },
  { path: '/admin/departments/new', requires: PAGE_PERMISSIONS.departments, element: <AdminDepartmentFormPage /> },
  { path: '/admin/departments/:id/edit', requires: PAGE_PERMISSIONS.departments, element: <AdminDepartmentFormPage /> },
  { path: '/admin/buildings', requires: PAGE_PERMISSIONS.buildings, element: <AdminBuildingsPage /> },
  { path: '/admin/buildings/new', requires: PAGE_PERMISSIONS.buildings, element: <AdminBuildingFormPage /> },
  { path: '/admin/buildings/:id/edit', requires: PAGE_PERMISSIONS.buildings, element: <AdminBuildingFormPage /> },
  { path: '/admin/floors', requires: PAGE_PERMISSIONS.floors, element: <AdminFloorsPage /> },
  { path: '/admin/floors/new', requires: PAGE_PERMISSIONS.floors, element: <AdminFloorFormPage /> },
  { path: '/admin/floors/:id/edit', requires: PAGE_PERMISSIONS.floors, element: <AdminFloorFormPage /> },
  { path: '/admin/host-employees', requires: PAGE_PERMISSIONS.hostEmployees, element: <AdminHostEmployeesPage /> },
  { path: '/admin/host-employees/new', requires: PAGE_PERMISSIONS.hostEmployees, element: <AdminHostEmployeeFormPage /> },
  { path: '/admin/host-employees/:id/edit', requires: PAGE_PERMISSIONS.hostEmployees, element: <AdminHostEmployeeFormPage /> },
  { path: '/admin/reception-desks', requires: PAGE_PERMISSIONS.receptionDesks, element: <AdminReceptionDesksPage /> },
  { path: '/admin/reception-desks/*', element: <Navigate to="/admin/reception-desks" replace /> },
  { path: '/admin/security-gates', requires: PAGE_PERMISSIONS.securityGates, element: <AdminSecurityGatesPage /> },
  { path: '/admin/security-gates/*', element: <Navigate to="/admin/security-gates" replace /> },
  { path: '/admin/kiosks', requires: PAGE_PERMISSIONS.kiosks, element: <AdminKiosksPage /> },
  { path: '/admin/kiosks/new', requires: PAGE_PERMISSIONS.kiosks, element: <AdminKioskFormPage /> },
  { path: '/admin/kiosks/:id/edit', requires: PAGE_PERMISSIONS.kiosks, element: <AdminKioskFormPage /> },
  { path: '/admin/visitor-categories', requires: PAGE_PERMISSIONS.visitorCategories, element: <AdminVisitorCategoriesPage /> },
  { path: '/admin/visitor-categories/new', requires: PAGE_PERMISSIONS.visitorCategories, element: <AdminVisitorCategoryFormPage /> },
  { path: '/admin/visitor-categories/:id/edit', requires: PAGE_PERMISSIONS.visitorCategories, element: <AdminVisitorCategoryFormPage /> },
  { path: '/admin/workflows', requires: PAGE_PERMISSIONS.workflows, element: <AdminWorkflowsPage /> },
  { path: '/admin/workflows/new', requires: PAGE_PERMISSIONS.workflows, element: <AdminWorkflowFormPage /> },
  { path: '/admin/workflows/:visitorCategoryId/edit', requires: PAGE_PERMISSIONS.workflows, element: <AdminWorkflowFormPage /> },
  { path: '/admin/badge-printing', requires: PAGE_PERMISSIONS.badgePrinting, element: <ReceptionBadgePrintingPage /> },
  { path: '/admin/invitations', requires: PAGE_PERMISSIONS.adminInvitations, element: <AdminInvitationsPage /> },
  {
    path: '/admin/calendar',
    requires: PAGE_PERMISSIONS.calendar,
    element: <CalendarPage boardBasePath="/admin/invitations" />,
  },
  { path: '/admin/roles', requires: PAGE_PERMISSIONS.roles, element: <AdminRolesPage /> },
  { path: '/admin/roles/new', requires: PAGE_PERMISSIONS.roles, element: <AdminRoleCreateFormPage /> },
  { path: '/admin/roles/:id/edit', requires: PAGE_PERMISSIONS.roles, element: <AdminRolePermissionsFormPage /> },
  { path: '/admin/form-builder', requires: PAGE_PERMISSIONS.formBuilder, element: <AdminFormBuilderPage /> },
  { path: '/admin/form-builder/steps/:stepId', requires: PAGE_PERMISSIONS.formBuilder, element: <AdminFormBuilderStepEditorPage /> },
  { path: '/admin/audit-trail', requires: PAGE_PERMISSIONS.auditTrail, element: <AdminAuditTrailPage /> },
]

const STAFF_ROUTES: PageRoute[] = [
  {
    path: '/staff/dashboard',
    element: <StaffDashboardPage />,
  },
  // Under the staff layout so reception shares its top bar, refresh control
  // and current-user context; the page keeps its own Reception-role guard.
  {
    path: '/reception/dashboard',
    element: <ReceptionDashboardPage />,
  },
  { path: '/reception/badge-printing', requires: PAGE_PERMISSIONS.badgePrinting, element: <ReceptionBadgePrintingPage /> },
  { path: '/staff/invitations', requires: PAGE_PERMISSIONS.staffInvitations, element: <StaffInvitationsPage /> },
  {
    path: '/staff/calendar',
    requires: PAGE_PERMISSIONS.calendar,
    element: <CalendarPage boardBasePath="/staff/invitations" />,
  },
  { path: '/staff/visitors/new', requires: PAGE_PERMISSIONS.registerVisitor, element: <StaffVisitorRegistrationPage /> },
]

function renderPageRoutes(routes: PageRoute[]) {
  return routes.map(({ path, element, requires }) => (
    <Route key={path} path={path} element={<RequirePermission requires={requires}>{element}</RequirePermission>} />
  ))
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
                {/* Covers a lazy layout's own first load; once a layout is
                    mounted, its Suspense covers its pages. */}
                <Suspense fallback={<LoadingState label="Loading…" className="min-h-dvh" />}>
                  <Routes>
                    <Route element={<PublicLayout />}>
                      <Route path="/" element={<VisitorPortalLandingPage />} />
                      <Route path="/visitor/request" element={<VisitorRequestPage />} />
                      <Route path="/visitor/track" element={<VisitorTrackPage />} />
                      <Route path="/badge/scan" element={<BadgeScanPage />} />
                      <Route path="/admin/login" element={<StaffLoginPage />} />
                      <Route path="/staff/login" element={<StaffSsoLoginPage />} />
                      <Route path="*" element={<NotFoundPage />} />
                    </Route>

                    <Route element={<AdminLayout />}>{renderPageRoutes(ADMIN_ROUTES)}</Route>

                    <Route element={<StaffLayout />}>{renderPageRoutes(STAFF_ROUTES)}</Route>
                  </Routes>
                </Suspense>
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
const router = createBrowserRouter([{ path: '*', element: <RootLayout />, errorElement: <RouteErrorPage /> }])

function App() {
  return <RouterProvider router={router} />
}

export default App
