import { useRef, type ReactNode } from 'react'
import { XIcon } from '../icons'
import { useFocusTrap } from '../../hooks/use-focus-trap'
import { usePresence } from '../../hooks/use-presence'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  maxWidthClassName?: string
}

export function Modal({ isOpen, onClose, title, children, maxWidthClassName = 'max-w-md' }: ModalProps) {
  // Stays mounted through its exit animation (ui-motion "Modal dialogs and
  // sheets animate in and out"); `data-state` drives the backdrop fade and
  // the panel's sheet-up (below `sm`) / scale-in (from `sm`) keyframes in
  // index.css.
  const { isMounted, state, onAnimationEnd } = usePresence(isOpen)
  const panelRef = useRef<HTMLDivElement>(null)
  // Escape closes, Tab stays inside, and focus returns to the opener once
  // the dialog starts closing.
  useFocusTrap(panelRef, isMounted && isOpen, onClose)

  // Callers usually clear the state their dialog renders from (e.g.
  // `pendingDelete`) in the same update that closes it, so the exit
  // animation would otherwise show "undefined" or an empty form. While
  // closing, keep rendering the last open frame's title and content.
  const lastOpenViewRef = useRef({ title, children })
  if (isOpen) lastOpenViewRef.current = { title, children }
  const view = isOpen ? { title, children } : lastOpenViewRef.current

  if (!isMounted) return null

  const isClosing = state === 'closing'

  // Below `sm` the dialog is a bottom sheet spanning the full width; from `sm`
  // up it's the centered card it always was. The title row and — by
  // convention, every modal's last child is its row of action buttons — the
  // actions row stay pinned while the body scrolls between them
  // (responsive-layout "Modals Fit Small Screens").
  // Both pinned rows use negative offsets (-top-*/-bottom-*) equal to the
  // dialog's padding: sticky offsets are measured from the padding-inset
  // edge, so `bottom-0` would lift the actions a padding-width over the body.
  return (
    <div
      data-state={state}
      // `inert` while closing: an exiting dialog takes no clicks or focus.
      inert={isClosing}
      className="motion-backdrop fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={view.title}
        data-state={state}
        onAnimationEnd={onAnimationEnd}
        className={`motion-dialog flex max-h-[92dvh] w-full ${maxWidthClassName} flex-col gap-5 overflow-y-auto rounded-t-2xl bg-surface p-4 shadow-lg sm:max-h-[90vh] sm:rounded-2xl sm:p-6 [&>*:last-child:has(>button)]:sticky [&>*:last-child:has(>button)]:-bottom-4 [&>*:last-child:has(>button)]:-mx-4 [&>*:last-child:has(>button)]:-mb-4 [&>*:last-child:has(>button)]:flex-wrap [&>*:last-child:has(>button)]:border-t [&>*:last-child:has(>button)]:border-border-subtle [&>*:last-child:has(>button)]:bg-surface [&>*:last-child:has(>button)]:px-4 [&>*:last-child:has(>button)]:py-3 sm:[&>*:last-child:has(>button)]:-bottom-6 sm:[&>*:last-child:has(>button)]:-mx-6 sm:[&>*:last-child:has(>button)]:-mb-6 sm:[&>*:last-child:has(>button)]:px-6 sm:[&>*:last-child:has(>button)]:py-4`}
      >
        <div className="sticky -top-4 z-10 -mx-4 -mt-4 flex items-center justify-between gap-3 bg-surface px-4 pt-4 pb-1 sm:-top-6 sm:-mx-6 sm:-mt-6 sm:px-6 sm:pt-6">
          <h2 className="min-w-0 font-display text-lg font-bold text-text">{view.title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex size-10 shrink-0 items-center justify-center rounded-full text-text-faint transition-colors duration-fast hover:bg-border-subtle lg:size-7"
          >
            <XIcon className="size-4" />
          </button>
        </div>
        {view.children}
      </div>
    </div>
  )
}
