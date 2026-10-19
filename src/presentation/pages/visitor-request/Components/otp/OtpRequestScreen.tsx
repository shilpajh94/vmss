import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { PendingButton } from '../../../../components/ui/PendingButton'
import type { RegistrationType } from '../../types'

interface OtpRequestScreenProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  contact: string
  onContactChange: (value: string) => void
  contactError?: string
  requestErrorMessage?: string
  loading: boolean
  onSubmit: () => void
}

export function OtpRequestScreen({
  registrationType,
  onRegistrationTypeChange,
  contact,
  onContactChange,
  contactError,
  requestErrorMessage,
  loading,
  onSubmit,
}: OtpRequestScreenProps) {
  return (
    <div className="flex h-fit w-full max-w-[480px] flex-col gap-6 rounded-2xl border border-border bg-surface p-5 md:p-8 shadow-[0_4px_8px_rgba(15,23,42,0.03)]">
      <h3 className="font-display text-[22px] font-bold text-text">Request a visit</h3>

      <div className="flex flex-col gap-1.5">
        <span className="text-body font-medium text-text">
          Registration type<span className="text-danger">*</span>
        </span>
        <SegmentedToggle
          options={[
            { value: 'individual', label: 'Single visitor' },
            { value: 'group', label: 'Group visitors' },
          ]}
          value={registrationType}
          onChange={(value) => onRegistrationTypeChange(value as RegistrationType)}
          variant="pill"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-body font-medium text-text" htmlFor="otp-contact">
          Visitor&apos;s mobile number / email ID<span className="text-danger">*</span>
        </label>
        <input
          id="otp-contact"
          type="text"
          value={contact}
          onChange={(event) => onContactChange(event.target.value)}
          placeholder="Enter Mobile Number / Email ID"
          className={`rounded-lg border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
            contactError ? 'border-danger' : 'border-border'
          }`}
        />
        {contactError && <p className="text-caption text-danger">{contactError}</p>}
      </div>

      {requestErrorMessage && <p className="text-caption text-danger">{requestErrorMessage}</p>}

      <PendingButton
        onClick={onSubmit}
        pending={loading}
        pendingLabel="Requesting…"
        className="flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white transition-colors enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Request OTP
      </PendingButton>
    </div>
  )
}
