import { Toast } from './Toast'
import type { ToastItem } from './toast-context'

interface ToastViewportProps {
  toasts: ToastItem[]
  onDismiss: (id: string) => void
}

export function ToastViewport({ toasts, onDismiss }: ToastViewportProps) {
  if (toasts.length === 0) return null

  return (
    // No flex gap: each toast carries its own bottom spacing inside its
    // collapsing slot (index.css `.motion-toast`), so when one leaves the
    // ones below glide up the full distance instead of jumping the last 8px.
    <div className="pointer-events-none fixed top-4 right-4 left-4 z-50 items-end sm:left-auto flex flex-col">
      {toasts.map((toast) => (
        <div key={toast.id} data-state={toast.isClosing ? 'closing' : 'open'} inert={toast.isClosing} className="motion-toast pointer-events-auto">
          <div className="pb-2">
            <Toast toast={toast} onDismiss={onDismiss} />
          </div>
        </div>
      ))}
    </div>
  )
}
