import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { TextField } from '../ui/TextField'
import { confirmSubject } from '../../utils/confirm-subject'
import { formatDateTime } from '../../utils/format-time'
import { todayAsDateInputValue } from '../../utils/local-date-input-value'
import { FormConfirmStep } from './FormConfirmStep'

interface RescheduleInvitationModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isRescheduling?: boolean
  onConfirm: (preferredVisitDate: string, preferredVisitTime: string) => void
  onCancel: () => void
}

// A visit is never rescheduled into the past, whatever its status (the API
// enforces this for an archived no-show; gap G29 covers the rest).
export function RescheduleInvitationModal({ isOpen, visitorName, trackingId, isRescheduling, onConfirm, onCancel }: RescheduleInvitationModalProps) {
  const [preferredVisitDate, setPreferredVisitDate] = useState('')
  const [preferredVisitTime, setPreferredVisitTime] = useState('')
  const [isConfirming, setIsConfirming] = useState(false)
  const minDate = todayAsDateInputValue()
  // `min` only limits the picker; a typed date can still be earlier.
  const isPastDate = preferredVisitDate !== '' && preferredVisitDate < minDate

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
            error={isPastDate ? 'Choose today or a later date.' : undefined}
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
              disabled={!preferredVisitDate || !preferredVisitTime || isPastDate}
              onClick={() => setIsConfirming(true)}
              className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
            >
              Review change
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
