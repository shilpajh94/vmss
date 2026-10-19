import { createContext, useCallback, useContext, useMemo, useReducer, type ReactNode } from 'react'
import { ToastViewport } from './ToastViewport'
import { MOTION_MS } from '../../utils/motion'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastOptions {
  // When provided, the toast becomes clickable and invokes this instead of
  // just being a passive message (e.g. a push notification linking to its invitation).
  onClick?: () => void
}

export interface ToastItem {
  id: string
  variant: ToastVariant
  message: string
  onClick?: () => void
  // Set once dismissed: the toast plays its exit animation (and its slot
  // collapses so the rest glide up) before it is removed for real.
  isClosing?: boolean
}

type ToastAction = { type: 'ADD'; toast: ToastItem } | { type: 'CLOSE'; id: string } | { type: 'REMOVE'; id: string }

function toastReducer(state: ToastItem[], action: ToastAction): ToastItem[] {
  if (action.type === 'ADD') return [...state, action.toast]
  if (action.type === 'CLOSE') return state.map((toast) => (toast.id === action.id ? { ...toast, isClosing: true } : toast))
  return state.filter((toast) => toast.id !== action.id)
}

// Exit animation length plus slack (ui-motion "Toasts animate in and out").
const EXIT_MS = MOTION_MS.standard + 50

// Errors get more reading time than success/info before they auto-dismiss.
const AUTO_DISMISS_MS: Record<ToastVariant, number> = {
  success: 4000,
  info: 4000,
  error: 6000,
}

interface ToastContextValue {
  success: (message: string, options?: ToastOptions) => void
  error: (message: string, options?: ToastOptions) => void
  info: (message: string, options?: ToastOptions) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, dispatch] = useReducer(toastReducer, [] as ToastItem[])

  // Dismissing twice (click, then the auto-dismiss timer) is harmless:
  // CLOSE is idempotent and REMOVE of a missing id is a no-op.
  const dismiss = useCallback((id: string) => {
    dispatch({ type: 'CLOSE', id })
    setTimeout(() => dispatch({ type: 'REMOVE', id }), EXIT_MS)
  }, [])

  const show = useCallback(
    (variant: ToastVariant, message: string, options?: ToastOptions) => {
      const id = crypto.randomUUID()
      dispatch({ type: 'ADD', toast: { id, variant, message, onClick: options?.onClick } })
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS[variant])
    },
    [dismiss],
  )

  const success = useCallback((message: string, options?: ToastOptions) => show('success', message, options), [show])
  const error = useCallback((message: string, options?: ToastOptions) => show('error', message, options), [show])
  const info = useCallback((message: string, options?: ToastOptions) => show('info', message, options), [show])

  // Stable identity so consumers that put `useToast()`'s return value in a dependency
  // array (e.g. a data-loading useCallback) don't re-run every time a toast is added.
  const value = useMemo(() => ({ success, error, info }), [success, error, info])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }

  return context
}
