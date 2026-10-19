import { useEffect, useRef, useState } from 'react'
import { AlertCircleIcon, CheckIcon, InfoIcon, XIcon } from '../icons'
import { AUTO_DISMISS_MS, type ToastItem } from './toast-context'

const VARIANT_CONFIG = {
  success: { border: 'border-l-success', icon: 'text-success', Icon: CheckIcon, role: 'status' as const },
  error: { border: 'border-l-danger', icon: 'text-danger', Icon: AlertCircleIcon, role: 'alert' as const },
  info: { border: 'border-l-info', icon: 'text-info', Icon: InfoIcon, role: 'status' as const },
}

// Once the pointer and focus leave a paused toast, it stays at least this
// long so the user isn't racing it (notifications "Notifications
// auto-dismiss but can be dismissed early").
const RESUME_MIN_MS = 2000

// A grouped summary's count can change several times a second during a
// burst; screen readers hear it only once it has settled this long.
const ANNOUNCE_SETTLE_MS = 1000

interface ToastProps {
  toast: ToastItem
  onDismiss: (id: string) => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  const { border, icon, Icon, role } = VARIANT_CONFIG[toast.variant]
  const durationMs = AUTO_DISMISS_MS[toast.variant]
  const isGrouped = Boolean(toast.groupKey)

  const [isPointerInside, setIsPointerInside] = useState(false)
  const [isFocusInside, setIsFocusInside] = useState(false)
  const isPaused = isPointerInside || isFocusInside
  const remainingMsRef = useRef(durationMs)
  const wasPausedRef = useRef(false)

  // A toast only mounts once it is visible, so a queued toast's duration
  // starts here, not when it was shown. Each push joining a group restarts
  // it. Declared before the timer effect so its reset lands before re-arming.
  useEffect(() => {
    remainingMsRef.current = durationMs
    wasPausedRef.current = false
  }, [toast.groupVersion, durationMs])

  useEffect(() => {
    if (isPaused) {
      wasPausedRef.current = true
      return
    }
    const startedAt = Date.now()
    const delay = wasPausedRef.current ? Math.max(remainingMsRef.current, RESUME_MIN_MS) : remainingMsRef.current
    const timeoutId = window.setTimeout(() => onDismiss(toast.id), delay)
    return () => {
      window.clearTimeout(timeoutId)
      remainingMsRef.current = Math.max(0, delay - (Date.now() - startedAt))
    }
  }, [isPaused, toast.groupVersion, toast.id, durationMs, onDismiss])

  const [announcedMessage, setAnnouncedMessage] = useState(toast.message)
  useEffect(() => {
    if (!isGrouped) return
    const timeoutId = window.setTimeout(() => setAnnouncedMessage(toast.message), ANNOUNCE_SETTLE_MS)
    return () => window.clearTimeout(timeoutId)
  }, [isGrouped, toast.message])

  const handleActivate = () => {
    toast.onClick?.()
    onDismiss(toast.id)
  }

  return (
    <div
      // A grouped toast's text changes in place, so its live region is the
      // settled copy below instead of the whole toast.
      role={isGrouped ? undefined : role}
      aria-live={isGrouped ? undefined : role === 'alert' ? 'assertive' : 'polite'}
      onPointerEnter={() => setIsPointerInside(true)}
      onPointerLeave={() => setIsPointerInside(false)}
      onFocus={() => setIsFocusInside(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsFocusInside(false)
      }}
      className={`flex w-[calc(100vw-2rem)] items-start sm:w-[360px] gap-3 rounded-lg border border-border border-l-4 bg-surface p-4 shadow-[0_4px_8px_rgba(15,23,42,0.08)] ${border}`}
    >
      {isGrouped && (
        <span role={role} aria-live="polite" className="sr-only">
          {announcedMessage}
        </span>
      )}
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
