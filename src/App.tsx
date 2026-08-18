import { BrowserRouter, Route, Routes } from 'react-router'
import { AppDependenciesProvider } from './presentation/context/app-dependencies-context'
import { ToastProvider } from './presentation/components/toast/toast-context'
import { VisitorPortalLandingPage } from './presentation/pages/visitor-portal-landing/visitor-portal-landing'
import { VisitorRequestPage } from './presentation/pages/visitor-request/visitor-request'
import { VisitorTrackPage } from './presentation/pages/visitor-track/visitor-track'
import { StaffLoginPage } from './presentation/pages/staff-login/staff-login'
import { StaffDashboardPage } from './presentation/pages/staff-dashboard/staff-dashboard'
import { StaffVisitorRegistrationPage } from './presentation/pages/staff-visitor-registration/staff-visitor-registration'
import { StaffAuditTrailPage } from './presentation/pages/staff-audit-trail/staff-audit-trail'
import { AdminOrganisationConfigsPage } from './presentation/pages/admin-organisation-configs/admin-organisation-configs'
import { AdminBranchesPage } from './presentation/pages/admin-branches/admin-branches'
import { AdminBranchCreatePage } from './presentation/pages/admin-branches/admin-branch-create'
import { AdminDepartmentsPage } from './presentation/pages/admin-departments/admin-departments'
import { AdminDepartmentFormPage } from './presentation/pages/admin-departments/admin-department-form'
import { AdminBuildingsPage } from './presentation/pages/admin-buildings/admin-buildings'
import { AdminBuildingFormPage } from './presentation/pages/admin-buildings/admin-building-form'
import { AdminFloorsPage } from './presentation/pages/admin-floors/admin-floors'
import { AdminFloorFormPage } from './presentation/pages/admin-floors/admin-floor-form'

function RootLayout() {
  return (
    <ToastProvider>
      <AppDependenciesProvider>
        <Routes>
          <Route path="/" element={<VisitorPortalLandingPage />} />
          <Route path="/visitor/request" element={<VisitorRequestPage />} />
          <Route path="/visitor/track" element={<VisitorTrackPage />} />
          <Route path="/staff/login" element={<StaffLoginPage />} />
          <Route path="/staff/dashboard" element={<StaffDashboardPage />} />
          <Route path="/staff/visitors/new" element={<StaffVisitorRegistrationPage />} />
          <Route path="/staff/audit-trail" element={<StaffAuditTrailPage />} />
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
        </Routes>
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
