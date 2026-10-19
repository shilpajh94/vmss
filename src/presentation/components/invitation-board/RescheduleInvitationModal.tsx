import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { TextField } from '../ui/TextField'
import { confirmSubject } from '../../utils/confirm-subject'
import { formatDateTime } from '../../utils/format-time'
import { FormConfirmStep } from './FormConfirmStep'

interface RescheduleInvitationModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isRescheduling?: boolean
  /** Earliest selectable date (YYYY-MM-DD) — set for an archived no-show, which the API only reschedules to today or later. */
  minDate?: string
  onConfirm: (preferredVisitDate: string, preferredVisitTime: string) => void
  onCancel: () => void
}

export function RescheduleInvitationModal({ isOpen, visitorName, trackingId, isRescheduling, minDate, onConfirm, onCancel }: RescheduleInvitationModalProps) {
  const [preferredVisitDate, setPreferredVisitDate] = useState('')
  const [preferredVisitTime, setPreferredVisitTime] = useState('')
  const [isConfirming, setIsConfirming] = useState(false)

  const reset = () => {
    setPreferredVisitDate('')
    setPreferredVisitTime('')
    setIsConfirming(false)
  }

  const handleCancel = () => {
    if (isRescheduling) return
    reset()
    onCancel()
  }

  const handleConfirm = () => {
    onConfirm(preferredVisitDate, preferredVisitTime)
    reset()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Reschedule Visit">
      {isConfirming ? (
        <FormConfirmStep
          message={`Reschedule the visit for ${confirmSubject(visitorName, trackingId)}?`}
          rows={[{ label: 'New date & time', value: formatDateTime(`${preferredVisitDate}T${preferredVisitTime}`) }]}
          confirmLabel="Reschedule Visit"
          busyLabel="Rescheduling…"
          isBusy={isRescheduling}
          onBack={() => setIsConfirming(false)}
          onConfirm={handleConfirm}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <TextField
            label="New date"
            labelClassName="font-body text-[13px] font-semibold text-text"
            type="date"
            min={minDate}
            value={preferredVisitDate}
            onChange={setPreferredVisitDate}
          />
          <TextField
            label="New time"
            labelClassName="font-body text-[13px] font-semibold text-text"
            type="time"
            value={preferredVisitTime}
            onChange={setPreferredVisitTime}
          />

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
              disabled={!preferredVisitDate || !preferredVisitTime}
              onClick={() => setIsConfirming(true)}
              className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
            >
              Review change
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
