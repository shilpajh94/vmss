import { Modal } from '../ui/Modal'
import { PendingButton } from '../ui/PendingButton'
import { confirmSubject } from '../../utils/confirm-subject'

interface CheckOutVisitorModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isCheckingOut?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function CheckOutVisitorModal({ isOpen, visitorName, trackingId, isCheckingOut, onConfirm, onCancel }: CheckOutVisitorModalProps) {
  const subject = visitorName ? confirmSubject(visitorName, trackingId) : 'this visitor'

  return (
    <Modal isOpen={isOpen} onClose={isCheckingOut ? () => undefined : onCancel} title="Check Out Visitor">
      <div className="flex flex-col gap-3">
        <p className="font-body text-sm text-text-muted">Check out {subject}? This marks the visit as ended.</p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            disabled={isCheckingOut}
            onClick={onCancel}
            className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-50"
          >
            Cancel
          </button>
          <PendingButton
            pending={isCheckingOut}
            pendingLabel="Checking out…"
            onClick={onConfirm}
            className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
          >
            Check Out
          </PendingButton>
        </div>
      </div>
    </Modal>
  )
}
