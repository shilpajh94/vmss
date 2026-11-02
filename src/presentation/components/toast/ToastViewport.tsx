import { Toast } from './Toast'
import type { ToastItem } from './toast-context'

// notifications "At most three notifications are visible at once": the rest
// wait, in order, until a visible one leaves.
const MAX_VISIBLE_TOASTS = 3

interface ToastViewportProps {
  toasts: ToastItem[]
  onDismiss: (id: string) => void
  // A closing toast's exit animation has finished.
  onExited: (id: string) => void
}

function selectRendered(toasts: ToastItem[]): ToastItem[] {
  let openCount = 0
  return toasts.filter((toast) => {
    // A closing toast keeps its slot until its exit animation ends.
    if (toast.isClosing) return true
    openCount += 1
    return openCount <= MAX_VISIBLE_TOASTS
  })
}

export function ToastViewport({ toasts, onDismiss, onExited }: ToastViewportProps) {
  if (toasts.length === 0) return null

  return (
    // Anchored bottom-right (bottom edge on phones) so a toast never covers
    // the top bar's controls; the newest sits closest to the edge. No flex
    // gap: each toast carries its own top spacing inside its collapsing slot
    // (index.css `.motion-toast`), so when one leaves the others glide the
    // full distance instead of jumping the last 8px.
    <div className="pointer-events-none fixed right-4 bottom-4 left-4 z-50 flex flex-col items-end sm:left-auto">
      {selectRendered(toasts).map((toast) => (
        <div
          key={toast.id}
          data-state={toast.isClosing ? 'closing' : 'open'}
          inert={toast.isClosing}
          onAnimationEnd={(event) => {
            if (toast.isClosing && event.animationName === 'motion-fade-out') onExited(toast.id)
          }}
          className="motion-toast pointer-events-auto"
        >
          <div className="pt-2">
            <Toast toast={toast} onDismiss={onDismiss} />
          </div>
        </div>
      ))}
    </div>
  )
}
