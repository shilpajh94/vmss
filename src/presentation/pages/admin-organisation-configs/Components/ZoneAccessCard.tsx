import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { useZoneAccessSetting } from '../hooks/use-zone-access-setting'

export function ZoneAccessCard() {
  const { enabled, canManage, isLoading, errorMessage, isSaving, retry, change } = useZoneAccessSetting()

  if (!canManage) return null

  return (
    <section className="flex w-full max-w-[536px] flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">Zone Access Control</h2>
      <p className="font-body text-[13px] text-text-muted">
        When on, you can define zones, choose which zones each visit may enter, and guards can scan badges at zone gates. With no zones
        mapped to a visit or its category, every zone is denied. When off, all zone screens are hidden.
      </p>

      {errorMessage ? (
        <div role="alert" className="flex items-center gap-3">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={() => void retry()} className="font-body text-[13px] font-semibold text-admin-accent">
            Try again
          </button>
        </div>
      ) : isLoading || enabled === undefined ? (
        <p role="status" className="font-body text-sm text-text-muted">
          Loading…
        </p>
      ) : (
        <div className={isSaving ? 'pointer-events-none opacity-60' : undefined}>
          <ToggleSwitch label="Enable zone access control" checked={enabled} onChange={(next) => void change(next)} />
        </div>
      )}
    </section>
  )
}
