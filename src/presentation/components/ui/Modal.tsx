import type { ReactNode } from 'react'
import { XIcon } from '../icons'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  maxWidthClassName?: string
}

export function Modal({ isOpen, onClose, title, children, maxWidthClassName = 'max-w-md' }: ModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className={`flex max-h-[90vh] w-full ${maxWidthClassName} flex-col gap-5 overflow-y-auto rounded-2xl bg-surface p-6 shadow-lg`}>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex size-7 items-center justify-center rounded-full text-text-faint hover:bg-border-subtle"
          >
            <XIcon className="size-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
