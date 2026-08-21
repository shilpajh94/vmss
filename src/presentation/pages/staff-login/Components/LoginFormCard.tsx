import { TextField } from '../../../components/ui/TextField'

interface LoginFormCardProps {
  email: string
  password: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => void
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
      className="flex w-[460px] flex-col gap-8 rounded-2xl border border-border bg-surface p-12 drop-shadow-[0_16px_16px_rgba(15,23,42,0.05)]"
    >
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

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2.5 rounded-lg bg-secondary-accent px-6 py-3.5 font-body text-[15px] font-semibold text-white drop-shadow-[0_4px_6px_rgba(6,182,212,0.15)] disabled:opacity-60"
        >
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
        {errorMessage && <p className="font-body text-[13px] text-danger">{errorMessage}</p>}
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
