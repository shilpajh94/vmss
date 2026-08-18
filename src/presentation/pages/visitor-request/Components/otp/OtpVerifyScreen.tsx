import { Spinner } from '../../../../components/ui/LoadingState'

interface OtpVerifyScreenProps {
  code: string
  onCodeChange: (value: string) => void
  codeError?: string
  verifyErrorMessage?: string
  loading: boolean
  onSubmit: () => void
  onUseDifferentContact: () => void
}

export function OtpVerifyScreen({
  code,
  onCodeChange,
  codeError,
  verifyErrorMessage,
  loading,
  onSubmit,
  onUseDifferentContact,
}: OtpVerifyScreenProps) {
  return (
    <div className="flex h-fit w-[480px] flex-col gap-6 rounded-2xl border border-border bg-surface p-8 shadow-[0_4px_8px_rgba(15,23,42,0.03)]">
      <h3 className="font-display text-[22px] font-bold text-text">Request a visit</h3>

      <div className="flex items-start gap-2 rounded-lg bg-[#ecfeff] px-4 py-3 text-body text-text">
        <svg
          width="18"
          height="18"
          viewBox="0 0 20 20"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="mt-0.5 shrink-0 text-secondary-accent"
        >
          <path
            d="M10 2L16.5 4.5V9.5C16.5 13.5 13.7 16.9 10 18C6.3 16.9 3.5 13.5 3.5 9.5V4.5L10 2Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M7.5 10L9.3 11.8L12.8 8.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>If that contact is valid, a verification code has been sent to it.</span>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-body font-medium text-text" htmlFor="otp-code">
          Verification code<span className="text-danger">*</span>
        </label>
        <input
          id="otp-code"
          type="text"
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          className={`rounded-lg border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
            codeError ? 'border-danger' : 'border-border'
          }`}
        />
        {codeError && <p className="text-caption text-danger">{codeError}</p>}
      </div>

      {verifyErrorMessage && <p className="text-caption text-danger">{verifyErrorMessage}</p>}

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading}
        className="flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white disabled:opacity-60"
      >
        {loading && <Spinner className="size-4 border-white/40 border-t-white" />}
        {loading ? 'Verifying…' : 'Verify and continue'}
      </button>

      <button type="button" onClick={onUseDifferentContact} className="text-left text-body font-semibold text-secondary-accent">
        Use a different number or email
      </button>
    </div>
  )
}
