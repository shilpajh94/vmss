import { createContext, useCallback, useContext, useMemo, useReducer, type ReactNode } from 'react'
import { ToastViewport } from './ToastViewport'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastItem {
  id: string
  variant: ToastVariant
  message: string
}

type ToastAction = { type: 'ADD'; toast: ToastItem } | { type: 'REMOVE'; id: string }

function toastReducer(state: ToastItem[], action: ToastAction): ToastItem[] {
  if (action.type === 'ADD') return [...state, action.toast]
  return state.filter((toast) => toast.id !== action.id)
}

// Errors get more reading time than success/info before they auto-dismiss.
const AUTO_DISMISS_MS: Record<ToastVariant, number> = {
  success: 4000,
  info: 4000,
  error: 6000,
}

interface ToastContextValue {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, dispatch] = useReducer(toastReducer, [] as ToastItem[])

  const dismiss = useCallback((id: string) => dispatch({ type: 'REMOVE', id }), [])

  const show = useCallback((variant: ToastVariant, message: string) => {
    const id = crypto.randomUUID()
    dispatch({ type: 'ADD', toast: { id, variant, message } })
    setTimeout(() => dispatch({ type: 'REMOVE', id }), AUTO_DISMISS_MS[variant])
  }, [])

  const success = useCallback((message: string) => show('success', message), [show])
  const error = useCallback((message: string) => show('error', message), [show])
  const info = useCallback((message: string) => show('info', message), [show])

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
