import { BrowserRouter, Route, Routes } from 'react-router'
import { AppDependenciesProvider } from './presentation/context/app-dependencies-context'
import { VisitorPortalLandingPage } from './presentation/pages/visitor-portal-landing/visitor-portal-landing'
import { VisitorRequestPage } from './presentation/pages/visitor-request/visitor-request'
import { VisitorTrackPage } from './presentation/pages/visitor-track/visitor-track'

function RootLayout() {
  return (
    <AppDependenciesProvider>
      <Routes>
        <Route path="/" element={<VisitorPortalLandingPage />} />
        <Route path="/visitor/request" element={<VisitorRequestPage />} />
        <Route path="/visitor/track" element={<VisitorTrackPage />} />
      </Routes>
    </AppDependenciesProvider>
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
