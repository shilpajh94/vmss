import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { AUTH_PRIMARY_BUTTON_CLASS, AuthErrorAlert, AuthFormHeading } from '../../../../components/auth/AuthFormParts'
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
    <div className="flex w-full flex-col gap-6">
      <AuthFormHeading title="Request a visit" />

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
          className={`min-h-10 rounded-lg border px-3 py-2 text-body text-text max-sm:text-base placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
            contactError ? 'border-danger' : 'border-border'
          }`}
        />
        {contactError && <p className="text-caption text-danger">{contactError}</p>}
      </div>

      {requestErrorMessage && <AuthErrorAlert message={requestErrorMessage} />}

      <PendingButton
        onClick={onSubmit}
        pending={loading}
        pendingLabel="Requesting…"
        className={`cursor-pointer disabled:cursor-not-allowed ${AUTH_PRIMARY_BUTTON_CLASS}`}
      >
        Request OTP
      </PendingButton>
    </div>
  )
}
