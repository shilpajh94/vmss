import { AlertCircleIcon, CheckIcon, InfoIcon, XIcon } from '../icons'
import type { ToastItem } from './toast-context'

const VARIANT_CONFIG = {
  success: { border: 'border-l-success', icon: 'text-success', Icon: CheckIcon, role: 'status' as const },
  error: { border: 'border-l-danger', icon: 'text-danger', Icon: AlertCircleIcon, role: 'alert' as const },
  info: { border: 'border-l-info', icon: 'text-info', Icon: InfoIcon, role: 'status' as const },
}

interface ToastProps {
  toast: ToastItem
  onDismiss: (id: string) => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  const { border, icon, Icon, role } = VARIANT_CONFIG[toast.variant]

  const handleActivate = () => {
    toast.onClick?.()
    onDismiss(toast.id)
  }

  return (
    <div
      role={role}
      aria-live={role === 'alert' ? 'assertive' : 'polite'}
      className={`flex w-[360px] items-start gap-3 rounded-lg border border-border border-l-4 bg-surface p-4 shadow-[0_4px_8px_rgba(15,23,42,0.08)] ${border}`}
    >
      <Icon className={`size-5 shrink-0 ${icon}`} />
      {toast.onClick ? (
        <button
          type="button"
          onClick={handleActivate}
          className="min-w-0 flex-1 text-left font-body text-sm text-text hover:underline"
        >
          {toast.message}
        </button>
      ) : (
        <p className="min-w-0 flex-1 font-body text-sm text-text">{toast.message}</p>
      )}
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="shrink-0 text-text-faint hover:text-text"
      >
        <XIcon className="size-4" />
      </button>
    </div>
  )
}
