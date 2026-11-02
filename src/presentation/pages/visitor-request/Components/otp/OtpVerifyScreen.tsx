import { AUTH_PRIMARY_BUTTON_CLASS, AuthErrorAlert, AuthFormHeading } from '../../../../components/auth/AuthFormParts'
import { PendingButton } from '../../../../components/ui/PendingButton'

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
    <div className="flex w-full flex-col gap-6">
      <AuthFormHeading title="Request a visit" />

      <div className="flex items-start gap-2 rounded-lg bg-secondary-accent-soft px-4 py-3 text-body text-text">
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
          inputMode="numeric"
          autoComplete="one-time-code"
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          className={`min-h-10 rounded-lg border px-3 py-2 text-body text-text max-sm:text-base placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
            codeError ? 'border-danger' : 'border-border'
          }`}
        />
        {codeError && <p className="text-caption text-danger">{codeError}</p>}
      </div>

      {verifyErrorMessage && <AuthErrorAlert message={verifyErrorMessage} />}

      <PendingButton
        onClick={onSubmit}
        title="Verify the code sent to your contact and continue"
        pending={loading}
        pendingLabel="Verifying…"
        className={`cursor-pointer disabled:cursor-not-allowed ${AUTH_PRIMARY_BUTTON_CLASS}`}
      >
        Verify and continue
      </PendingButton>

      <button
        type="button"
        onClick={onUseDifferentContact}
        className="cursor-pointer text-left text-body font-semibold text-secondary-accent hover:underline"
      >
        Use a different number or email
      </button>
    </div>
  )
}
