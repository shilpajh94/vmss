import { KeyIcon } from '../../../../assets/icons'
import { AUTH_PRIMARY_BUTTON_CLASS, AuthErrorAlert, AuthFormHeading, AuthSecurityNote } from '../../../components/auth/AuthFormParts'
import { PendingButton } from '../../../components/ui/PendingButton'
import type { StaffSsoLoginStatus } from '../hooks/use-staff-sso-login-page'

interface SsoSignInCardProps {
  status: StaffSsoLoginStatus
  errorMessage?: string
  onSignIn: () => void
}

export function SsoSignInCard({ status, errorMessage, onSignIn }: SsoSignInCardProps) {
  const isBusy = status === 'redirecting' || status === 'completing'

  return (
    <div className="flex w-full flex-col gap-6 xshort:gap-4">
      <AuthFormHeading title="Welcome back" description="Sign in with your organization credentials" />

      <div className="flex flex-col gap-4 xshort:gap-3">
        {errorMessage && <AuthErrorAlert message={errorMessage} />}
        <PendingButton
          onClick={onSignIn}
          pending={isBusy}
          pendingLabel={status === 'completing' ? 'Completing sign-in…' : 'Redirecting…'}
          className={`cursor-pointer disabled:cursor-not-allowed ${AUTH_PRIMARY_BUTTON_CLASS}`}
        >
          <img src={KeyIcon} alt="" className="size-[18px]" />
          Sign in with SSO
        </PendingButton>
      </div>

      <AuthSecurityNote text="Secured by corporate multi-factor authentication" />
    </div>
  )
}
