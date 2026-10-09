import { BrowserRouter, Route, Routes } from 'react-router'
import { AppDependenciesProvider } from './presentation/context/app-dependencies-context'
import { ToastProvider } from './presentation/components/toast/toast-context'
import { PushNotificationsProvider } from './presentation/components/push-notifications/PushNotificationsProvider'
import { SessionExpiryListener } from './presentation/components/session/SessionExpiryListener'
import { PublicLayout } from './presentation/components/PublicLayout'
import { AdminLayout } from './presentation/components/AdminLayout'
import { StaffLayout } from './presentation/components/StaffLayout'
import { NotificationCenterProvider } from './presentation/context/notification-center-context'
import { VisitorPortalLandingPage } from './presentation/pages/visitor-portal-landing/visitor-portal-landing'
import { VisitorRequestPage } from './presentation/pages/visitor-request/visitor-request'
import { VisitorTrackPage } from './presentation/pages/visitor-track/visitor-track'
import { StaffLoginPage } from './presentation/pages/staff-login/staff-login'
import { StaffSsoLoginPage } from './presentation/pages/staff-sso-login/staff-sso-login'
import { StaffDashboardPage } from './presentation/pages/staff-dashboard/staff-dashboard'
import { StaffVisitorRegistrationPage } from './presentation/pages/staff-visitor-registration/staff-visitor-registration'
import { AdminDashboardPage } from './presentation/pages/admin-dashboard/admin-dashboard'
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
import { AdminReceptionDeskFormPage } from './presentation/pages/admin-reception-desks/admin-reception-desk-form'
import { AdminSecurityGatesPage } from './presentation/pages/admin-security-gates/admin-security-gates'
import { AdminSecurityGateFormPage } from './presentation/pages/admin-security-gates/admin-security-gate-form'
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
import { ReceptionDashboardPage } from './presentation/pages/reception-dashboard/reception-dashboard'

function RootLayout() {
  return (
    <ToastProvider>
      <AppDependenciesProvider>
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

              <Route path="/reception/dashboard" element={<ReceptionDashboardPage />} />

              <Route element={<AdminLayout />}>
                <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
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
                <Route path="/admin/reception-desks/new" element={<AdminReceptionDeskFormPage />} />
                <Route path="/admin/reception-desks/:id/edit" element={<AdminReceptionDeskFormPage />} />
                <Route path="/admin/security-gates" element={<AdminSecurityGatesPage />} />
                <Route path="/admin/security-gates/new" element={<AdminSecurityGateFormPage />} />
                <Route path="/admin/security-gates/:id/edit" element={<AdminSecurityGateFormPage />} />
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
                <Route path="/admin/roles" element={<AdminRolesPage />} />
                <Route path="/admin/roles/new" element={<AdminRoleCreateFormPage />} />
                <Route path="/admin/roles/:id/edit" element={<AdminRolePermissionsFormPage />} />
                <Route path="/admin/form-builder" element={<AdminFormBuilderPage />} />
                <Route path="/admin/form-builder/steps/:stepId" element={<AdminFormBuilderStepEditorPage />} />
                <Route path="/admin/audit-trail" element={<AdminAuditTrailPage />} />
              </Route>

              <Route element={<StaffLayout />}>
                <Route path="/staff/dashboard" element={<StaffDashboardPage />} />
                <Route path="/staff/visitors/new" element={<StaffVisitorRegistrationPage />} />
              </Route>
            </Routes>
          </PushNotificationsProvider>
        </NotificationCenterProvider>
      </AppDependenciesProvider>
    </ToastProvider>
  )
}

function App() {
  return (
    <BrowserRouter>
      <RootLayout />
    </BrowserRouter>
  )
}

export default App
