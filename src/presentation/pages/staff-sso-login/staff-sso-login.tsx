import { AuthSplitLayout } from '../../components/auth/AuthSplitLayout'
import { SsoSignInCard } from './Components/SsoSignInCard'
import { useStaffSsoLoginPage } from './hooks/use-staff-sso-login-page'

export function StaffSsoLoginPage() {
  const { status, errorMessage, startSso } = useStaffSsoLoginPage()

  return (
    <AuthSplitLayout portalLabel="Staff Portal">
      <SsoSignInCard status={status} errorMessage={errorMessage} onSignIn={startSso} />
    </AuthSplitLayout>
  )
}
