import { useEffect, useMemo, useRef, useState } from 'react'
import { usePageHeader } from '../../context/page-header-context'
import { useCurrentUser } from '../../context/current-user-context'
import { useBranchOptions } from '../../hooks/use-branch-options'
import { DashboardLoadError } from '../../components/dashboard/DashboardStates'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
import { CalendarIcon } from '../../components/icons'
import { CalendarToolbar } from './components/CalendarToolbar'
import { DayAgenda } from './components/DayAgenda'
import { MonthGrid } from './components/MonthGrid'
import { WeekBoard } from './components/WeekBoard'
import { useCalendarFeed } from './hooks/use-calendar-feed'
import { useCalendarState } from './hooks/use-calendar-state'
import { PER_DAY_LIMIT } from './calendar-status'
import type { BoardBasePath } from '../../components/dashboard/dashboard-format'
import type { CalendarFeed } from '../../../domain/entities/calendar-feed-schema'
import type { BranchOption } from '../../hooks/use-branch-options'

const LOAD_ERROR = 'Something went wrong loading the calendar. Please try again.'

interface CalendarPageProps {
  loginPath: '/admin/login' | '/staff/login'
  boardBasePath: BoardBasePath
}

// What the subtitle says the calendar is showing — always the scope the API
// applied, never a guess from the user's role flags (staff-calendar spec).
function scopeSubtitle(feed: CalendarFeed, branchId: string | undefined, branchOptions: BranchOption[]): string {
  if (feed.scope === 'mine') return 'Your visits'
  if (branchId) {
    const name = branchOptions.find((branch) => branch.id === branchId)?.name
    return name ? `All visits at ${name}` : 'All visits at the selected branch'
  }
  if (branchOptions.length > 1) return 'All visits at all your branches'
  // A single-branch viewer gets no selector (and so no branch list); its one
  // branch name comes with the visits themselves.
  const names = new Set(feed.events.map((event) => event.branchName).filter((name): name is string => Boolean(name)))
  return names.size === 1 ? `All visits at ${[...names][0]}` : 'All visits at your branch'
}

function CalendarSkeleton() {
  return (
    <div role="status" aria-label="Loading calendar…" aria-busy="true" className="flex w-full flex-col gap-4">
      <Skeleton className="h-28 w-full rounded-2xl" />
      <Skeleton className="h-[480px] w-full rounded-2xl" />
    </div>
  )
}

// The staff and admin Calendar page (add-staff-calendar). One component for
// both portals; the API decides which visits the signed-in user sees.
export function CalendarPage({ loginPath, boardBasePath }: CalendarPageProps) {
  const currentUser = useCurrentUser()
  // The visit timezone, learned from the first response; "today" follows it.
  const [timezone, setTimezone] = useState<string | undefined>(undefined)
  const state = useCalendarState(timezone)
  const { feed, isStale, hasCurrentError, hasInitialError, isInitialLoading, retry } = useCalendarFeed({
    range: state.range,
    branchId: state.branchId,
    statuses: state.statuses,
    perDayLimit: PER_DAY_LIMIT[state.view],
    loginPath,
  })
  const branchOptions = useBranchOptions(currentUser, feed?.scope === 'branch')

  useEffect(() => {
    if (feed && feed.timezone !== timezone) setTimezone(feed.timezone)
  }, [feed, timezone])

  usePageHeader({ description: 'Visits and invitations by date' })

  const totalVisits = useMemo(() => feed?.days.reduce((sum, day) => sum + day.total, 0) ?? 0, [feed])

  // The Week board and (from `lg` up) the Day card size themselves to the
  // space left below this block and re-measure when it wraps
  // (fix-paging-footers-and-calendar-day-scroll design.md D3).
  const controlsRef = useRef<HTMLDivElement>(null)
  const isEmptyRange = state.view !== 'day' && totalVisits === 0

  if (hasInitialError || (hasCurrentError && !feed)) return <DashboardLoadError message={LOAD_ERROR} onRetry={retry} />
  if (isInitialLoading || !feed) return <CalendarSkeleton />

  return (
    <div className="flex w-full min-w-0 flex-col gap-4 md:gap-6">
      <div ref={controlsRef} className="flex flex-col gap-4 md:gap-6">
        <header className="flex flex-col gap-1">
          <h1 className="font-display text-2xl font-semibold text-text">Calendar</h1>
          <p className="font-body text-sm text-text-muted">{scopeSubtitle(feed, state.branchId, branchOptions)}</p>
        </header>

        <CalendarToolbar
          view={state.view}
          date={state.date}
          onViewChange={state.setView}
          onShift={state.shift}
          onToday={state.goToday}
          branchOptions={feed.scope === 'branch' ? branchOptions : []}
          branchId={state.branchId}
          onBranchChange={state.selectBranch}
          selectedStatuses={state.selectedStatuses}
          onToggleStatus={state.toggleStatus}
        />
      </div>

      {hasCurrentError ? (
        // The newly chosen view, branch or filter failed; the toolbar stays
        // usable so the user can pick another.
        <DashboardLoadError message={LOAD_ERROR} onRetry={retry} />
      ) : feed.from !== state.range.from || feed.to !== state.range.to ? (
        // A different range is loading: the old one's days don't fit this view.
        <Skeleton className="h-[480px] w-full rounded-2xl" />
      ) : (
        <div aria-busy={isStale} className={`flex w-full min-w-0 flex-col gap-4 transition-opacity duration-fast ${isStale ? 'pointer-events-none opacity-60' : ''}`}>
          {isEmptyRange ? (
            <div className="rounded-2xl border border-border bg-surface">
              <EmptyState
                message={state.view === 'month' ? 'No visits this month.' : 'No visits this week.'}
                icon={<CalendarIcon className="size-4 text-text-muted" />}
                className="py-6"
              />
            </div>
          ) : null}
          {state.view === 'month' ? (
            <MonthGrid feed={feed} anchorDate={state.date} today={state.today} boardBasePath={boardBasePath} onOpenDay={state.openDay} />
          ) : state.view === 'week' ? (
            <WeekBoard
              feed={feed}
              today={state.today}
              branchId={state.branchId}
              statuses={state.statuses}
              boardBasePath={boardBasePath}
              onOpenDay={state.openDay}
              controlsRef={controlsRef}
              remeasureKey={isEmptyRange}
            />
          ) : (
            <DayAgenda
              feed={feed}
              branchId={state.branchId}
              statuses={state.statuses}
              boardBasePath={boardBasePath}
              controlsRef={controlsRef}
            />
          )}
        </div>
      )}
    </div>
  )
}
