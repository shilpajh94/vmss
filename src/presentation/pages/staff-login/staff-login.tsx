import { HeroImage } from '../../components/HeroImage'
import { LoginFormCard } from './Components/LoginFormCard'
import { StaffGatewayHeader } from './Components/StaffGatewayHeader'
import { StaffLoginFooter } from './Components/StaffLoginFooter'
import { useStaffLoginPage } from './hooks/use-staff-login-page'
import { SUPPORT_EMAIL } from '../../brand'

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
    <div className="relative flex h-dvh w-full flex-col overflow-hidden">
      <div aria-hidden className="absolute inset-0">
        <HeroImage />
        <div className="absolute inset-0 bg-primary/55" />
      </div>

      <StaffGatewayHeader />

      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="flex min-h-full flex-col items-center justify-center gap-4 md:gap-6 xshort:gap-3 md:xshort:gap-3 px-4 md:px-12 py-6 md:py-8 xshort:py-4 md:xshort:py-4">
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
          {SUPPORT_EMAIL && (
            <div className="flex items-center gap-4 font-body text-[13px]">
              <span className="font-medium text-[#cbd5e1]">Need help?</span>
              <a href={`mailto:${SUPPORT_EMAIL}`} className="font-semibold text-secondary-accent underline">
                Contact System Administrator
              </a>
            </div>
          )}
        </div>
      </main>

      <StaffLoginFooter />
    </div>
  )
}
