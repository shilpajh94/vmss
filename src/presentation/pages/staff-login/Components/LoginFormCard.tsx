import { KeyIcon } from '../../../../assets/icons'
import { PendingButton } from '../../../components/ui/PendingButton'
import { TextField } from '../../../components/ui/TextField'

interface LoginFormCardProps {
  email: string
  password: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => void
  onSsoSignIn: () => void
  loading: boolean
  errorMessage?: string
  emailError?: string
  passwordError?: string
}

export function LoginFormCard({
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onSsoSignIn,
  loading,
  errorMessage,
  emailError,
  passwordError,
}: LoginFormCardProps) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
      className="flex w-full max-w-[460px] flex-col gap-6 md:gap-8 md:short:gap-6 xshort:gap-4 md:xshort:gap-4 rounded-2xl border border-border bg-surface p-6 md:p-12 md:short:p-8 md:xshort:py-6 drop-shadow-[0_16px_16px_rgba(15,23,42,0.05)]"
    >
      <div className="flex flex-col items-center gap-4 xshort:gap-2">
        <span className="rounded-full bg-[#ecfeff] px-3 py-1 font-body text-[12px] font-bold tracking-[1px] text-secondary-accent uppercase">
          Admin Portal
        </span>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="font-display text-[28px] font-bold text-text">Enterprise Sign In</h1>
          <p className="font-body text-[14px] leading-normal text-text-muted">Sign in with your organization credentials</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 xshort:gap-3">
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={onEmailChange}
          placeholder="Enter your email"
          required
          error={emailError}
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={onPasswordChange}
          placeholder="Enter your password"
          required
          error={passwordError}
        />

        <PendingButton
          type="submit"
          pending={loading}
          pendingLabel="Signing in…"
          className="flex w-full items-center justify-center gap-2.5 rounded-lg bg-secondary-accent px-6 py-3.5 font-body text-[15px] font-semibold text-white drop-shadow-[0_4px_6px_rgba(6,182,212,0.15)] disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
        >
          Sign In
        </PendingButton>
        {errorMessage && <p className="font-body text-[13px] text-danger">{errorMessage}</p>}

        <div className="flex items-center gap-3">
          <span className="h-px flex-1 bg-border" />
          <span className="font-body text-[12px] text-text-faint">or</span>
          <span className="h-px flex-1 bg-border" />
        </div>

        <button
          type="button"
          onClick={onSsoSignIn}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2.5 rounded-lg border border-border bg-surface px-6 py-3.5 font-body text-[15px] font-semibold text-text disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
        >
          <img src={KeyIcon} alt="" className="size-[18px]" />
          Sign in with SSO
        </button>
      </div>

      <div className="flex items-center justify-center gap-2 pt-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0 text-text-faint" aria-hidden>
          <path
            d="M12 2 4 5v6c0 5 3.4 8.4 8 11 4.6-2.6 8-6 8-11V5l-8-3Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <p className="text-center font-body text-[12px] text-text-faint">Secured by corporate authentication</p>
      </div>
    </form>
  )
}
