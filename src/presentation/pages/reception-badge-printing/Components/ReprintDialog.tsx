import type { CheckinSearchRow } from '../../../../domain/entities/checkin-schema'
import { Modal } from '../../../components/ui/Modal'
import { PendingButton } from '../../../components/ui/PendingButton'
import { TextareaField } from '../../../components/ui/TextareaField'
import { REASON_MAX } from '../hooks/use-badge-printing'

interface ReprintDialogProps {
  target: CheckinSearchRow | undefined
  reason: string
  reasonValid: boolean
  busy: boolean
  onReasonChange: (value: string) => void
  onCancel: () => void
  onConfirm: () => void
}

// Reprinting is a state-changing GET: it kills the previous badge's QR at
// once, so it only ever runs from this dialog's confirm button.
export function ReprintDialog({ target, reason, reasonValid, busy, onReasonChange, onCancel, onConfirm }: ReprintDialogProps) {
  return (
    <Modal isOpen={target !== undefined} onClose={busy ? () => undefined : onCancel} title="Reprint badge">
      <p className="text-body text-text-muted">
        Reprint the badge for {target?.fullName}? The previous badge stops working immediately.
      </p>
      <TextareaField
        label="Reason for reprint"
        value={reason}
        onChange={onReasonChange}
        placeholder="e.g. lost, damaged"
        rows={3}
        required
        maxLength={REASON_MAX}
        disabled={busy}
      />
      <p className="text-caption text-text-muted">
        {reason.trim().length}/{REASON_MAX}
      </p>
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text max-lg:min-h-10 disabled:opacity-50"
        >
          Cancel
        </button>
        <PendingButton
          pending={busy}
          pendingLabel="Reprinting…"
          disabled={!reasonValid}
          onClick={onConfirm}
          className="rounded-full bg-danger px-4 py-2 font-body text-[13px] font-semibold text-on-accent max-lg:min-h-10 disabled:opacity-50"
        >
          Reprint badge
        </PendingButton>
      </div>
    </Modal>
  )
}
