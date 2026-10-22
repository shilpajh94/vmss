import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { useKioskLocationValidation } from '../hooks/use-kiosk-location-validation'

export function KioskLocationValidationCard() {
  const { enforce, canManage, isVisible, isLoading, errorMessage, isSaving, retry, change } = useKioskLocationValidation()

  if (!isVisible) return null

  return (
    <section className="flex w-full max-w-[536px] flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">Kiosk Location Validation</h2>
      <p className="font-body text-[13px] text-text-muted">
        When on, a kiosk can only check visitors in at the branch and building it is registered to. Check-out is never restricted.
      </p>

      {errorMessage ? (
        <div role="alert" className="flex items-center gap-3">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={() => void retry()} className="font-body text-[13px] font-semibold text-admin-accent">
            Try again
          </button>
        </div>
      ) : isLoading || enforce === undefined ? (
        <p role="status" className="font-body text-sm text-text-muted">
          Loading…
        </p>
      ) : canManage ? (
        <div className={isSaving ? 'pointer-events-none opacity-60' : undefined}>
          <ToggleSwitch label="Enforce kiosk location validation" checked={enforce} onChange={(next) => void change(next)} />
        </div>
      ) : (
        <p className="font-body text-sm font-semibold text-text">
          Enforce kiosk location validation: {enforce ? 'On' : 'Off'}
        </p>
      )}
    </section>
  )
}
