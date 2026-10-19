import { PendingButton } from '../ui/PendingButton'

export interface ConfirmSummaryRow {
  label: string
  value: string
}

interface FormConfirmStepProps {
  message: string
  rows: ConfirmSummaryRow[]
  confirmLabel: string
  busyLabel: string
  isBusy?: boolean
  onBack: () => void
  onConfirm: () => void
}

// The second phase of a form-based invitation action (Reschedule, Edit,
// Delegate, Approve & Delegate): rendered inside the form's own Modal in
// place of the form, so "Back" returns to the still-mounted form with its
// input intact instead of stacking a second dialog.
export function FormConfirmStep({ message, rows, confirmLabel, busyLabel, isBusy, onBack, onConfirm }: FormConfirmStepProps) {
  return (
    <div className="flex flex-col gap-3">
      <p className="font-body text-sm text-text-muted">{message}</p>
      <dl className="flex flex-col gap-2 rounded-lg border border-border-subtle px-3 py-2">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
            <dt className="shrink-0 font-body text-[13px] font-semibold text-text sm:w-36">{row.label}</dt>
            <dd className="min-w-0 break-words font-body text-sm text-text-muted">{row.value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          disabled={isBusy}
          onClick={onBack}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-50"
        >
          Back
        </button>
        <PendingButton
          pending={isBusy}
          pendingLabel={busyLabel}
          onClick={onConfirm}
          className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
        >
          {confirmLabel}
        </PendingButton>
      </div>
    </div>
  )
}
