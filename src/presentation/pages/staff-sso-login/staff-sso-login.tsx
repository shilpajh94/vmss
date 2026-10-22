import { HeroImage } from '../../components/HeroImage'
import { SsoSignInCard } from './Components/SsoSignInCard'
import { StaffPortalHeader } from './Components/StaffPortalHeader'
import { StaffSsoLoginFooter } from './Components/StaffSsoLoginFooter'
import { useStaffSsoLoginPage } from './hooks/use-staff-sso-login-page'
import { SUPPORT_EMAIL } from '../../brand'

export function StaffSsoLoginPage() {
  const { status, errorMessage, startSso } = useStaffSsoLoginPage()

  return (
    <div className="relative flex h-dvh w-full flex-col overflow-hidden">
      <div aria-hidden className="absolute inset-0">
        <HeroImage />
        <div className="absolute inset-0 bg-primary/55" />
      </div>

      <StaffPortalHeader />

      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="flex min-h-full flex-col items-center justify-center gap-4 md:gap-6 xshort:gap-3 md:xshort:gap-3 px-4 md:px-12 py-6 md:py-8 xshort:py-4 md:xshort:py-4">
          <SsoSignInCard status={status} errorMessage={errorMessage} onSignIn={startSso} />
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

      <StaffSsoLoginFooter />
    </div>
  )
}
