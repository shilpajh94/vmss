import { useState } from 'react'
import { KeyIcon } from '../../../../assets/icons'
import { AUTH_PRIMARY_BUTTON_CLASS, AuthErrorAlert, AuthFormHeading, AuthSecurityNote } from '../../../components/auth/AuthFormParts'
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

const FIELD_LABEL_CLASS = 'font-body text-[13px] font-semibold text-text-secondary'

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
  const [showPassword, setShowPassword] = useState(false)

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
      className="flex w-full flex-col gap-6 xshort:gap-4"
    >
      <AuthFormHeading title="Welcome back" description="Sign in with your organization credentials" />

      <div className="flex flex-col gap-4 xshort:gap-3">
        {errorMessage && <AuthErrorAlert message={errorMessage} />}
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={onEmailChange}
          placeholder="name@company.com"
          required
          error={emailError}
          autoComplete="username"
          labelClassName={FIELD_LABEL_CLASS}
          inputClassName="py-3"
        />
        <TextField
          label="Password"
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={onPasswordChange}
          placeholder="Enter your password"
          required
          error={passwordError}
          autoComplete="current-password"
          labelClassName={FIELD_LABEL_CLASS}
          inputClassName="py-3"
          trailing={
            <button
              type="button"
              onClick={() => setShowPassword((shown) => !shown)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
              className="flex size-8 items-center justify-center rounded-md text-text-faint hover:text-text focus-visible:outline-2 focus-visible:outline-secondary-accent"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {showPassword && <path d="m3 3 18 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />}
              </svg>
            </button>
          }
        />

        <PendingButton type="submit" pending={loading} pendingLabel="Signing in…" className={`mt-1 ${AUTH_PRIMARY_BUTTON_CLASS}`}>
          Sign In
        </PendingButton>

        <div className="flex items-center gap-3">
          <span className="h-px flex-1 bg-border" />
          <span className="font-body text-[12px] text-text-faint">or</span>
          <span className="h-px flex-1 bg-border" />
        </div>

        <button
          type="button"
          onClick={onSsoSignIn}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2.5 rounded-lg border border-border-strong bg-surface px-6 py-3.5 font-body text-[15px] font-semibold text-text transition-colors duration-[var(--motion-fast)] hover:border-text-faint hover:bg-surface-muted disabled:opacity-60"
        >
          {/* The key SVG is drawn white for the cyan buttons; darken it on this outlined one. */}
          <img src={KeyIcon} alt="" className="size-[18px] brightness-0 opacity-75" />
          Sign in with SSO
        </button>
      </div>

      <AuthSecurityNote text="Secured by corporate authentication" />
    </form>
  )
}
