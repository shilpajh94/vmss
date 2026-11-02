import type { ReactNode } from 'react'

interface EmptyStateAction {
  label: string
  onClick: () => void
}

interface EmptyStateProps {
  message: string
  icon?: ReactNode
  action?: EmptyStateAction
  className?: string
}

export function EmptyState({ message, icon, action, className = '' }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 text-center ${className}`}>
      {icon && <span className="flex size-8 items-center justify-center rounded-full bg-surface-inset">{icon}</span>}
      <p className="font-body text-sm font-medium text-text-muted">{message}</p>
      {action && (
        <button type="button" onClick={action.onClick} className="rounded-lg bg-secondary-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
          {action.label}
        </button>
      )}
    </div>
  )
}
