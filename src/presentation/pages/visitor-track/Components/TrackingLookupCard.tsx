import { useId } from 'react'
import { SearchIcon } from '../../../../assets/icons'
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
      className="flex w-full max-w-[420px] flex-col gap-4 rounded-2xl border border-border bg-surface p-5 md:p-8 shadow-[0_4px_8px_rgba(15,23,42,0.03)]"
    >
      <div className="flex size-14 items-center justify-center rounded-xl bg-secondary-accent-soft">
        <img src={SearchIcon} alt="" className="size-7" />
      </div>
      <div>
        <h3 className="font-display text-[22px] font-bold text-text">Enter Your Tracking ID</h3>
        <p className="text-body text-text-muted">Use the tracking ID from your confirmation email.</p>
      </div>
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
        className="cursor-pointer rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white transition-colors enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Track Request
      </PendingButton>
    </form>
  )
}
