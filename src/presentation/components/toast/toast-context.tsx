import { createContext, useCallback, useContext, useMemo, useReducer, type ReactNode } from 'react'
import { ToastViewport } from './ToastViewport'
import { MOTION_MS } from '../../utils/motion'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastGroupSummary {
  message: string
  onClick?: () => void
}

export interface ToastOptions {
  // When provided, the toast becomes clickable and invokes this instead of
  // just being a passive message (e.g. a push notification linking to its invitation).
  onClick?: () => void
  // Toasts sharing a group key collapse into one: showing another while the
  // first is still open or queued updates that toast in place with
  // `groupSummary(count)` instead of adding one (notifications "A burst of
  // push notifications is grouped into one summary").
  groupKey?: string
  groupSummary?: (count: number) => ToastGroupSummary
}

export interface ToastItem {
  id: string
  variant: ToastVariant
  message: string
  onClick?: () => void
  groupKey?: string
  groupSummary?: (count: number) => ToastGroupSummary
  // How many shows this toast stands for, and a counter bumped on each one
  // so the toast restarts its auto-dismiss without remounting.
  groupCount: number
  groupVersion: number
  // Set once dismissed: the toast plays its exit animation (and its slot
  // collapses so the rest glide into it) before it is removed for real.
  isClosing?: boolean
}

type ToastAction = { type: 'ADD'; toast: ToastItem } | { type: 'CLOSE'; id: string } | { type: 'REMOVE'; id: string }

function toastReducer(state: ToastItem[], action: ToastAction): ToastItem[] {
  if (action.type === 'ADD') {
    const { groupKey } = action.toast
    const group = groupKey ? state.find((toast) => toast.groupKey === groupKey && !toast.isClosing) : undefined
    if (!group) return [...state, action.toast]

    const groupCount = group.groupCount + 1
    const groupSummary = action.toast.groupSummary ?? group.groupSummary
    const summary = groupSummary?.(groupCount) ?? { message: action.toast.message, onClick: action.toast.onClick }
    return state.map((toast) =>
      toast.id === group.id
        ? { ...toast, ...summary, onClick: summary.onClick, groupSummary, groupCount, groupVersion: toast.groupVersion + 1 }
        : toast,
    )
  }
  if (action.type === 'CLOSE') return state.map((toast) => (toast.id === action.id ? { ...toast, isClosing: true } : toast))
  return state.filter((toast) => toast.id !== action.id)
}

// Exit animation length plus slack (ui-motion "Toasts animate in and out"):
// the fallback removal when no `animationend` arrives.
// Read per dismissal, since the duration comes from the stylesheet.
const exitMs = () => MOTION_MS.standard + 50

// Errors get more reading time than success/info before they auto-dismiss.
// Each toast runs its own timer once it is actually visible (see Toast).
export const AUTO_DISMISS_MS: Record<ToastVariant, number> = {
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
  // CLOSE is idempotent and REMOVE of a missing id is a no-op. The toast
  // removes itself when its exit animation ends (`remove`); the timer is
  // only the fallback for when no animation runs (reduced motion).
  const dismiss = useCallback((id: string) => {
    dispatch({ type: 'CLOSE', id })
    setTimeout(() => dispatch({ type: 'REMOVE', id }), exitMs())
  }, [])

  const remove = useCallback((id: string) => dispatch({ type: 'REMOVE', id }), [])

  const show = useCallback((variant: ToastVariant, message: string, options?: ToastOptions) => {
    dispatch({
      type: 'ADD',
      toast: {
        id: crypto.randomUUID(),
        variant,
        message,
        onClick: options?.onClick,
        groupKey: options?.groupKey,
        groupSummary: options?.groupSummary,
        groupCount: 1,
        groupVersion: 0,
      },
    })
  }, [])

  const success = useCallback((message: string, options?: ToastOptions) => show('success', message, options), [show])
  const error = useCallback((message: string, options?: ToastOptions) => show('error', message, options), [show])
  const info = useCallback((message: string, options?: ToastOptions) => show('info', message, options), [show])

  // Stable identity so consumers that put `useToast()`'s return value in a dependency
  // array (e.g. a data-loading useCallback) don't re-run every time a toast is added.
  const value = useMemo(() => ({ success, error, info }), [success, error, info])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} onExited={remove} />
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
