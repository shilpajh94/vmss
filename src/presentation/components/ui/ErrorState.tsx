interface ErrorStateProps {
  message: string
  onRetry?: () => void
  className?: string
}

// The one failed-load state (async-ui-states, accessibility "Async Errors and
// Loading States Are Announced"): `role="alert"` makes a screen reader
// announce the failure without the user having to find it.
export function ErrorState({ message, onRetry, className = '' }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={`motion-content-in flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12 ${className}`}
    >
      <p className="font-body text-sm text-danger">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="min-h-10 rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent focus-visible:ring-2 focus-visible:ring-secondary-accent focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          Try again
        </button>
      )}
    </div>
  )
}
