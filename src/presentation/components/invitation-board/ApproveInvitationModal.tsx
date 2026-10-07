import { Modal } from '../ui/Modal'

interface ApproveInvitationModalProps {
  isOpen: boolean
  isApproving?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ApproveInvitationModal({ isOpen, isApproving, onConfirm, onCancel }: ApproveInvitationModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onCancel} title="Approve Visit Request">
      <div className="flex flex-col gap-3">
        <p className="font-body text-sm text-text-muted">Are you sure you want to approve this visit request?</p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isApproving}
            onClick={onConfirm}
            className="rounded-full bg-success px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
          >
            {isApproving ? 'Approving…' : 'Approve Request'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
