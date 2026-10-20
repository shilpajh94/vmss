import { CardSkeleton, KpiRowSkeleton, Skeleton } from '../ui/Skeleton'

// The full-page states a dashboard shows before it has any data.
export function DashboardLoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
      <p className="font-body text-sm text-danger">{message}</p>
      <button type="button" onClick={onRetry} className="min-h-10 rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
        Try again
      </button>
    </div>
  )
}

// Lays out the same rows the loaded dashboard renders (greeting card, KPI
// row, chart grids), with the charts' real plot heights, so the dashboard
// fills in place instead of jumping from a centred spinner
// (async-ui-states skeletons). `personal` is the staff "My" dashboard:
// greeting, KPIs, one chart row, and the upcoming list.
export function DashboardLoading({ variant = 'branch' }: { variant?: 'branch' | 'personal' }) {
  return (
    <div role="status" aria-label="Loading dashboard…" aria-busy="true" className="flex w-full flex-col gap-4 md:gap-6">
      <div aria-hidden className="flex w-full flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <Skeleton className="h-10 w-48 rounded-lg" />
      </div>
      <KpiRowSkeleton />
      <div aria-hidden className="grid w-full grid-cols-1 gap-4 md:gap-6 lg:grid-cols-12">
        <CardSkeleton className="lg:col-span-8" bodyClassName="h-[244px] md:h-[284px] lg:h-[304px]" />
        <CardSkeleton className="lg:col-span-4" bodyClassName="h-[244px] md:h-[284px] lg:h-[304px]" />
      </div>
      {variant === 'branch' ? (
        <div aria-hidden className="grid w-full grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
          <CardSkeleton bodyClassName="h-[200px] md:h-[240px]" />
          <CardSkeleton bodyClassName="h-[200px] md:h-[240px]" />
        </div>
      ) : (
        <CardSkeleton bodyClassName="h-40" />
      )}
    </div>
  )
}
