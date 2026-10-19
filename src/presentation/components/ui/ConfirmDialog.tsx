import type { ReactNode } from 'react'
import { Modal } from './Modal'
import { PendingButton } from './PendingButton'

type ConfirmTone = 'danger' | 'primary' | 'success'

const TONE_CLASSES: Record<ConfirmTone, string> = {
  danger: 'bg-danger',
  primary: 'bg-primary',
  success: 'bg-success',
}

interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  // Defaults keep the original look (a red confirm) for the admin CRUD
  // pages' delete confirmations.
  tone?: ConfirmTone
  // While true the dialog can't be confirmed again or dismissed, so a
  // double-click sends one request. The confirm button shows a spinner at
  // its normal width; `busyLabel` becomes its accessible name.
  isBusy?: boolean
  busyLabel?: string
  cancelLabel?: string
  // Optional summary rows (e.g. what a reschedule will change), shown under
  // the message.
  children?: ReactNode
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  tone = 'danger',
  isBusy = false,
  busyLabel,
  cancelLabel = 'Cancel',
  children,
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={isBusy ? () => undefined : onCancel} title={title}>
      <p className="text-body text-text-muted">{message}</p>
      {children}
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          disabled={isBusy}
          onClick={onCancel}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-50"
        >
          {cancelLabel}
        </button>
        <PendingButton
          pending={isBusy}
          pendingLabel={busyLabel}
          onClick={onConfirm}
          className={`rounded-full ${TONE_CLASSES[tone]} px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50`}
        >
          {confirmLabel}
        </PendingButton>
      </div>
    </Modal>
  )
}
