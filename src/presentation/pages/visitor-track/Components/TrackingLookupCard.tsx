import { useId } from 'react'
import { AUTH_PRIMARY_BUTTON_CLASS, AuthFormHeading } from '../../../components/auth/AuthFormParts'
import { PendingButton } from '../../../components/ui/PendingButton'

interface TrackingLookupCardProps {
  trackingId: string
  onTrackingIdChange: (value: string) => void
  onSubmit: () => void
  loading: boolean
  error?: string
}

// A real form, so Enter in the field submits the lookup.
export function TrackingLookupCard({ trackingId, onTrackingIdChange, onSubmit, loading, error }: TrackingLookupCardProps) {
  const inputId = useId()
  const errorId = `${inputId}-error`

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (!loading) onSubmit()
      }}
      className="flex w-full flex-col gap-5"
    >
      <AuthFormHeading title="Enter Your Tracking ID" description="Use the tracking ID from your confirmation email." />
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-body font-medium text-text">
          Tracking ID
        </label>
        <input
          id={inputId}
          type="text"
          value={trackingId}
          onChange={(event) => onTrackingIdChange(event.target.value)}
          placeholder="e.g. VIS-2026-00847"
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={`min-h-10 rounded-lg border px-3 py-2 text-body text-text max-sm:text-base placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
            error ? 'border-danger' : 'border-border'
          }`}
        />
        {error && (
          <p id={errorId} className="text-caption text-danger">
            {error}
          </p>
        )}
      </div>
      <PendingButton
        type="submit"
        title="Look up the status of your visit using your tracking ID"
        pending={loading}
        pendingLabel="Tracking…"
        className={`cursor-pointer disabled:cursor-not-allowed ${AUTH_PRIMARY_BUTTON_CLASS}`}
      >
        Track Request
      </PendingButton>
    </form>
  )
}
