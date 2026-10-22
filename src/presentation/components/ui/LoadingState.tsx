interface SpinnerProps {
  className?: string
}

export function Spinner({ className = '' }: SpinnerProps) {
  return <span aria-hidden className={`inline-block animate-spin rounded-full border-2 border-border-subtle border-t-secondary-accent ${className}`} />
}

interface LoadingStateProps {
  label?: string
  className?: string
}

export function LoadingState({ label = 'Loading…', className = '' }: LoadingStateProps) {
  return (
    // `role="status"` announces the wait to a screen reader (accessibility
    // "Async Errors and Loading States Are Announced").
    <div role="status" className={`flex flex-col items-center justify-center gap-3 ${className}`}>
      <Spinner className="size-6" />
      <p className="font-body text-sm text-text-muted">{label}</p>
    </div>
  )
}
