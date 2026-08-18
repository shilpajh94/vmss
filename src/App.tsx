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
