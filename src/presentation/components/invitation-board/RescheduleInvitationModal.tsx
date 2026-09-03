import { useState } from 'react'
import { Modal } from '../ui/Modal'

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
        <label className="flex flex-col gap-1.5">
          <span className="font-body text-[13px] font-semibold text-text">New date</span>
          <input
            type="date"
            value={preferredVisitDate}
            onChange={(event) => setPreferredVisitDate(event.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-body text-[13px] font-semibold text-text">New time</span>
          <input
            type="time"
            value={preferredVisitTime}
            onChange={(event) => setPreferredVisitTime(event.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text focus:outline-none"
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
