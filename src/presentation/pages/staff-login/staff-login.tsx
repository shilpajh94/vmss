import { AuthSplitLayout } from '../../components/auth/AuthSplitLayout'
import { LoginFormCard } from './Components/LoginFormCard'
import { useStaffLoginPage } from './hooks/use-staff-login-page'

export function StaffLoginPage() {
  const {
    email,
    password,
    setEmail,
    setPassword,
    status,
    errorMessage,
    emailError,
    passwordError,
    submitLogin,
    startSso,
  } = useStaffLoginPage()

  return (
    <AuthSplitLayout portalLabel="Admin Portal">
      <LoginFormCard
        email={email}
        password={password}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSubmit={submitLogin}
        onSsoSignIn={startSso}
        loading={status === 'submitting'}
        errorMessage={errorMessage}
        emailError={emailError}
        passwordError={passwordError}
      />
    </AuthSplitLayout>
  )
}
