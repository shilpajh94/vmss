import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { useBadgePrintFlowSetting } from '../hooks/use-badge-print-flow-setting'

export function BadgePrintFlowCard() {
  const { enabled, canManage, isLoading, errorMessage, isSaving, retry, change } = useBadgePrintFlowSetting()

  if (!canManage) return null

  return (
    <section className="flex w-full max-w-[536px] flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">Badge Printing</h2>
      <p className="font-body text-[13px] text-text-muted">
        When on, reception can print visitor badges after checking ID, and visitors are asked to bring ID. It only takes effect once badge
        printing is also enabled on the server.
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
          <ToggleSwitch label="Enable badge printing" checked={enabled} onChange={(next) => void change(next)} />
        </div>
      )}
    </section>
  )
}
