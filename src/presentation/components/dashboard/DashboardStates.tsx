import { LoadingState } from '../ui/LoadingState'

// The full-page states a dashboard shows before it has any data.
export function DashboardLoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
      <p className="font-body text-sm text-danger">{message}</p>
      <button type="button" onClick={onRetry} className="min-h-10 rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
        Try again
      </button>
    </div>
  )
}

export function DashboardLoading() {
  return <LoadingState label="Loading dashboard…" className="flex-1" />
}
