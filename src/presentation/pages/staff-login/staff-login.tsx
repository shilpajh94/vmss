import heroImage from '../../../assets/images/lobby-hero.png'
import { LoginFormCard } from './Components/LoginFormCard'
import { StaffGatewayHeader } from './Components/StaffGatewayHeader'
import { StaffLoginFooter } from './Components/StaffLoginFooter'
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
    <div className="relative flex min-h-screen w-full flex-col">
      <div aria-hidden className="absolute inset-0">
        <img src={heroImage} alt="" className="size-full object-cover" />
        <div className="absolute inset-0 bg-primary/55" />
      </div>

      <StaffGatewayHeader />

      <main className="relative flex flex-1 flex-col items-center justify-center gap-8 px-12 py-[120px]">
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
        <div className="flex items-center gap-4 font-body text-[13px]">
          <span className="font-medium text-[#cbd5e1]">Need help?</span>
          <a href="#" className="font-semibold text-secondary-accent underline">
            Contact System Administrator
          </a>
        </div>
      </main>

      <StaffLoginFooter />
    </div>
  )
}
