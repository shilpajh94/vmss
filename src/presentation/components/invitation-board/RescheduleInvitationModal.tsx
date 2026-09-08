import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { TextField } from '../ui/TextField'

interface RescheduleInvitationModalProps {
  isOpen: boolean
  isRescheduling?: boolean
  onConfirm: (preferredVisitDate: string, preferredVisitTime: string) => void
  onCancel: () => void
}

export function RescheduleInvitationModal({ isOpen, isRescheduling, onConfirm, onCancel }: RescheduleInvitationModalProps) {
  const [preferredVisitDate, setPreferredVisitDate] = useState('')
  const [preferredVisitTime, setPreferredVisitTime] = useState('')

  const handleCancel = () => {
    setPreferredVisitDate('')
    setPreferredVisitTime('')
    onCancel()
  }

  const handleConfirm = () => {
    onConfirm(preferredVisitDate, preferredVisitTime)
    setPreferredVisitDate('')
    setPreferredVisitTime('')
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Reschedule Visit">
      <div className="flex flex-col gap-3">
        <TextField
          label="New date"
          labelClassName="font-body text-[13px] font-semibold text-text"
          type="date"
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
            disabled={!preferredVisitDate || !preferredVisitTime || isRescheduling}
            onClick={handleConfirm}
            className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
          >
            {isRescheduling ? 'Rescheduling…' : 'Save new date & time'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
