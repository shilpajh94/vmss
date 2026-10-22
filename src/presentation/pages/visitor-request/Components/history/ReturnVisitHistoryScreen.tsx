import { Skeleton } from '../../../../components/ui/Skeleton'
import { PendingButton } from '../../../../components/ui/PendingButton'
import type { VisitHistoryEntry } from '../../../../../domain/entities/visitor-portal-schema'
import type { ReturningVisitorPortalStatus } from '../../hooks/use-returning-visitor-portal'

interface ReturnVisitHistoryScreenProps {
  status: ReturningVisitorPortalStatus
  history: VisitHistoryEntry[]
  errorMessage?: string
  hasMore: boolean
  onLoadMore: () => void
  onRetry: () => void
  onStartNewRequest: () => void
}

export function ReturnVisitHistoryScreen({
  status,
  history,
  errorMessage,
  hasMore,
  onLoadMore,
  onRetry,
  onStartNewRequest,
}: ReturnVisitHistoryScreenProps) {
  const isRetryableError = status === 'rate-limited' || status === 'misconfigured' || status === 'error'

  return (
    <div className="flex h-fit w-full max-w-[560px] flex-col gap-6 rounded-2xl border border-border bg-surface p-5 md:p-8 shadow-[0_4px_8px_rgba(15,23,42,0.03)]">
      <div>
        <h3 className="font-display text-[22px] font-bold text-text">Your recent visits</h3>
        <p className="mt-1 text-body text-text-muted">Review your past visits, or start a new request pre-filled with your details.</p>
      </div>

      {isRetryableError && (
        <div className="flex flex-col gap-3 rounded-lg bg-danger/10 px-4 py-3 text-body text-text">
          <span>
            {status === 'rate-limited'
              ? "You've made too many requests. Please wait a moment and try again."
              : status === 'misconfigured'
                ? 'This service is temporarily unavailable. Please try again shortly.'
                : 'Something went wrong loading your visits. Please try again.'}
          </span>
          {errorMessage && <span className="text-caption text-text-muted">{errorMessage}</span>}
          <button
            type="button"
            onClick={onRetry}
            className="cursor-pointer self-start text-body font-semibold text-secondary-accent hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {status === 'loading' && history.length === 0 && (
        // Shaped like the visit cards below, so they fill in place.
        <div role="status" aria-label="Loading your visits…" className="flex flex-col gap-3">
          {[0, 1, 2].map((row) => (
            <div key={row} className="flex flex-col gap-2 rounded-lg border border-border px-4 py-3">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-24" />
            </div>
          ))}
        </div>
      )}

      {!isRetryableError && history.length > 0 && (
        <ul className="flex flex-col gap-3">
          {history.map((visit) => (
            <li key={visit.trackingId} className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-body font-semibold text-text">{visit.trackingId}</span>
                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-caption font-medium text-primary">{visit.status}</span>
              </div>
              <span className="text-caption text-text-muted">{visit.purpose ?? 'No purpose recorded'}</span>
              <span className="text-caption text-text-muted">{visit.visitDate ?? 'Date unavailable'}</span>
            </li>
          ))}
        </ul>
      )}

      {!isRetryableError && status === 'loaded' && history.length === 0 && (
        <p className="text-body text-text-muted">No past visits found.</p>
      )}

      {hasMore && !isRetryableError && (
        <PendingButton
          onClick={onLoadMore}
          pending={status === 'loading'}
          pendingLabel="Loading…"
          className="cursor-pointer self-center text-body font-semibold text-secondary-accent hover:underline disabled:cursor-not-allowed disabled:opacity-60"
        >
          Load more
        </PendingButton>
      )}

      <button
        type="button"
        onClick={onStartNewRequest}
        title="Start a new visit request pre-filled with your details"
        className="cursor-pointer rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white transition-colors hover:opacity-90"
      >
        Start a new request
      </button>
    </div>
  )
}
