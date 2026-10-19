import { ConfirmDialog } from '../ui/ConfirmDialog'
import { confirmSubject } from '../../utils/confirm-subject'

interface ApproveInvitationModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isApproving?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ApproveInvitationModal({ isOpen, visitorName, trackingId, isApproving, onConfirm, onCancel }: ApproveInvitationModalProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      title="Approve Visit Request"
      message={`Approve the visit request for ${confirmSubject(visitorName, trackingId)}?`}
      confirmLabel="Approve Request"
      busyLabel="Approving…"
      tone="success"
      isBusy={isApproving}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  )
}
