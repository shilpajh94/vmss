import { KeyIcon, ShieldIcon } from '../../../../assets/icons'
import type { StaffSsoLoginStatus } from '../hooks/use-staff-sso-login-page'

interface SsoSignInCardProps {
  status: StaffSsoLoginStatus
  errorMessage?: string
  onSignIn: () => void
}

export function SsoSignInCard({ status, errorMessage, onSignIn }: SsoSignInCardProps) {
  const isBusy = status === 'redirecting' || status === 'completing'

  return (
    <div className="flex w-[460px] flex-col gap-8 rounded-2xl border border-border bg-surface p-12 drop-shadow-[0_16px_16px_rgba(15,23,42,0.05)]">
      <div className="flex flex-col items-center gap-4">
        <span className="rounded-full bg-[#ecfeff] px-3 py-1 font-body text-[12px] font-bold tracking-[1px] text-secondary-accent uppercase">
          Staff Portal
        </span>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="font-display text-[28px] font-bold text-text">Enterprise Sign In</h1>
          <p className="font-body text-[14px] leading-normal text-text-muted">Sign in with your organization credentials</p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={onSignIn}
          disabled={isBusy}
          className="flex w-full items-center justify-center gap-2.5 rounded-lg bg-secondary-accent px-6 py-3.5 font-body text-[15px] font-semibold text-white drop-shadow-[0_4px_6px_rgba(6,182,212,0.15)] disabled:opacity-60"
        >
          <img src={KeyIcon} alt="" className="size-[18px]" />
          {status === 'completing' ? 'Completing sign-in…' : status === 'redirecting' ? 'Redirecting…' : 'Sign in with SSO'}
        </button>
        {errorMessage && <p className="font-body text-[13px] text-danger">{errorMessage}</p>}
      </div>

      <div className="flex items-center justify-center gap-2 pt-2">
        <img src={ShieldIcon} alt="" className="size-3.5 shrink-0" />
        <p className="text-center font-body text-[12px] text-text-faint">Secured by corporate multi-factor authentication</p>
      </div>
    </div>
  )
}
