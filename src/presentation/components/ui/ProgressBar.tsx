interface ProgressBarProps {
  isActive: boolean
  className?: string
}

// Thin indeterminate bar along the top of a data region while it
// re-fetches (async-ui-states "Re-fetching keeps existing content
// visible"). Always rendered, with a negative bottom margin equal to its
// height, so showing or hiding it never moves the content beneath; it only
// fades. `sticky top-0` keeps it visible when the region is scrolled.
export function ProgressBar({ isActive, className = '' }: ProgressBarProps) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none sticky top-0 z-20 -mb-0.5 h-0.5 w-full shrink-0 overflow-hidden rounded-full bg-secondary-accent/15 transition-opacity duration-standard ${
        isActive ? 'opacity-100' : 'opacity-0'
      } ${className}`}
    >
      <div className={`h-full w-2/5 rounded-full bg-secondary-accent ${isActive ? 'progress-indeterminate' : ''}`} />
    </div>
  )
}
