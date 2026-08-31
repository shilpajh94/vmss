import { useState } from 'react'
import { Modal } from '../ui/Modal'

interface DenyInvitationModalProps {
  isOpen: boolean
  isDenying?: boolean
  onConfirm: (reason: string) => void
  onCancel: () => void
}

export function DenyInvitationModal({ isOpen, isDenying, onConfirm, onCancel }: DenyInvitationModalProps) {
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
          <button
            type="button"
            disabled={!reason.trim() || isDenying}
            onClick={handleConfirm}
            className="rounded-full bg-danger px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
          >
            {isDenying ? 'Denying…' : 'Deny Request'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
