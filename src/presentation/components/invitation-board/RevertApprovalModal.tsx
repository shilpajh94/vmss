import { useState } from 'react'
import { PendingButton } from '../ui/PendingButton'
import { Modal } from '../ui/Modal'
import { confirmSubject } from '../../utils/confirm-subject'

interface RevertApprovalModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isReverting?: boolean
  // Resolves `true` once the dialog has closed (reverted, or the visit had
  // already moved on), `false` if it stays open so the reason is kept for a
  // retry.
  onConfirm: (reason: string) => Promise<boolean>
  onCancel: () => void
}

export function RevertApprovalModal({ isOpen, visitorName, trackingId, isReverting, onConfirm, onCancel }: RevertApprovalModalProps) {
  const [reason, setReason] = useState('')

  const handleCancel = () => {
    if (isReverting) return
    setReason('')
    onCancel()
  }

  const handleConfirm = async () => {
    if (await onConfirm(reason.trim())) setReason('')
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Revert Approval">
      <div className="flex flex-col gap-3">
        <p className="font-body text-sm text-text-muted">
          Revert the approval for {confirmSubject(visitorName, trackingId)}? The request goes back to Requested for review, and the
          visitor's pass won't admit them until it's approved again.
        </p>
        <label className="flex flex-col gap-1.5">
          <span className="font-body text-[13px] font-semibold text-text">Reason for reverting</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            rows={3}
            placeholder="Explain why this approval is being reverted..."
            className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text placeholder:text-text-faint max-sm:text-base focus:outline-none focus:ring-2 focus:ring-secondary-accent"
          />
        </label>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            disabled={isReverting}
            onClick={handleCancel}
            className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-50"
          >
            Cancel
          </button>
          <PendingButton
            onClick={() => void handleConfirm()}
            pending={isReverting}
            pendingLabel="Reverting…"
            disabled={!reason.trim()}
            className="rounded-full bg-danger px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
          >
            Revert Approval
          </PendingButton>
        </div>
      </div>
    </Modal>
  )
}
