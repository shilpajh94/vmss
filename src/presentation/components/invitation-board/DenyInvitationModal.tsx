import { useState } from 'react'
import { PendingButton } from '../ui/PendingButton'
import { Modal } from '../ui/Modal'
import { confirmSubject } from '../../utils/confirm-subject'

interface DenyInvitationModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isDenying?: boolean
  onConfirm: (reason: string) => void
  onCancel: () => void
}

export function DenyInvitationModal({ isOpen, visitorName, trackingId, isDenying, onConfirm, onCancel }: DenyInvitationModalProps) {
  const [reason, setReason] = useState('')

  const handleCancel = () => {
    setReason('')
    onCancel()
  }

  const handleConfirm = () => {
    onConfirm(reason)
    setReason('')
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Deny Visit Request">
      <div className="flex flex-col gap-3">
        <p className="font-body text-sm text-text-muted">Deny the visit request for {confirmSubject(visitorName, trackingId)}?</p>
        <label className="flex flex-col gap-1.5">
          <span className="font-body text-[13px] font-semibold text-text">Reason for denial</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            rows={3}
            placeholder="Explain why this request is being denied..."
            className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text placeholder:text-text-faint focus:outline-none"
          />
        </label>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleCancel}
            className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
          >
            Cancel
          </button>
          <PendingButton
            onClick={handleConfirm}
            pending={isDenying}
            pendingLabel="Denying…"
            disabled={!reason.trim()}
            className="rounded-full bg-danger px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
          >
            Deny Request
          </PendingButton>
        </div>
      </div>
    </Modal>
  )
}
