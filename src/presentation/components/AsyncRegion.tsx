import type { ReactNode } from 'react'
import type { LoadPhase } from '../hooks/use-load-tracker'
import { ProgressBar } from './ui/ProgressBar'

interface AsyncRegionProps {
  phase: LoadPhase
  isRefreshing?: boolean
  /** Shown while nothing has loaded yet - a skeleton shaped like the content. */
  skeleton: ReactNode
  /** Shown only when the first load failed (a failed refresh keeps the content). */
  errorMessage?: string
  onRetry?: () => void
  /** True when the view loaded successfully with zero items. */
  isEmpty?: boolean
  empty?: ReactNode
  className?: string
  children: ReactNode
}

// The one place a data region decides between skeleton, error, empty, and
// content (async-ui-states), replacing each page's own ternary chain.
// Once loaded, the region never unmounts its content for a re-fetch: it
// dims it, blocks pointer input, and shows a progress bar until the new
// data swaps in place. Content and the empty state fade in when they
// replace a skeleton or each other.
export function AsyncRegion({
  phase,
  isRefreshing = false,
  skeleton,
  errorMessage = 'Something went wrong loading this page. Please try again.',
  onRetry,
  isEmpty = false,
  empty,
  className = '',
  children,
}: AsyncRegionProps) {
  if (phase === 'initial') return <>{skeleton}</>

  if (phase === 'error') {
    return (
      <div className="motion-content-in flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
        <p className="font-body text-sm text-danger">{errorMessage}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="min-h-10 rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
            Try again
          </button>
        )}
      </div>
    )
  }

  const showEmpty = isEmpty && empty !== undefined

  return (
    <div aria-busy={isRefreshing} className={`relative flex min-h-full flex-col ${className}`}>
      <ProgressBar isActive={isRefreshing} />
      <div
        // Re-keying on empty <-> content replays the fade-in for the swap.
        key={showEmpty ? 'empty' : 'content'}
        className={`motion-content-in flex min-h-0 flex-1 flex-col transition-opacity duration-standard ${
          isRefreshing ? 'pointer-events-none opacity-60' : 'opacity-100'
        }`}
      >
        {showEmpty ? empty : children}
      </div>
    </div>
  )
}
