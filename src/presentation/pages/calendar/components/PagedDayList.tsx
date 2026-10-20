import { useEffect, useMemo, useRef, type RefObject } from 'react'
import { CalendarEventChip } from './CalendarEventChip'
import { buildDayTimeline, slotLabel } from './calendar-grouping'
import type { DayPagesStatus } from '../hooks/use-day-pages'
import type { BoardBasePath } from '../../../components/dashboard/dashboard-format'
import type { CalendarEvent } from '../../../../domain/entities/calendar-feed-schema'

interface PagedDayListProps {
  events: CalendarEvent[]
  total: number
  status: DayPagesStatus
  onLoadMore: () => void
  // The element that scrolls this list (a week column's body); omitted, the
  // page's <main>.
  scrollRootRef?: RefObject<HTMLElement | null>
  boardBasePath: BoardBasePath
  timezone: string
  showHostAndBranch: boolean
  variant: 'block' | 'detail'
}

// One day's loaded visits on the working-hours timeline under sticky hour
// headings, with a sentinel right after the last loaded visit that loads the
// next page as it nears the scroll area, and a row for progress / loading /
// retry (staff-calendar "Month, week and day views with a working-hours
// timeline").
export function PagedDayList({
  events,
  total,
  status,
  onLoadMore,
  scrollRootRef,
  boardBasePath,
  timezone,
  showHostAndBranch,
  variant,
}: PagedDayListProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)
  const loadMoreRef = useRef(onLoadMore)
  loadMoreRef.current = onLoadMore
  const complete = events.length >= total
  const canLoad = status === 'idle' && !complete
  const timeline = useMemo(() => buildDayTimeline(events, complete), [events, complete])

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || !canLoad) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMoreRef.current()
      },
      { root: scrollRootRef?.current ?? null, rootMargin: '0px 0px 200px 0px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [canLoad, scrollRootRef, events.length])

  const progress = (
    <>
      <div ref={sentinelRef} aria-hidden className="h-px" />
      <DayListFooter loaded={events.length} total={total} status={status} onRetry={onLoadMore} />
    </>
  )

  return (
    <div className="flex flex-col">
      {total === 0 ? <p className="px-2 py-4 text-center font-body text-xs text-text-muted">No visits</p> : null}
      {timeline.frontier === -1 ? progress : null}
      {timeline.slots.map(({ slot, events: group }, index) => {
        const isBusy = group.length > 0
        return (
          <section key={slot} aria-label={slotLabel(slot)} className="flex flex-col">
            {variant === 'block' ? (
              // A label on a hairline rule rather than a filled bar, so a
              // column of mostly empty working hours stays light
              // (calendar-working-hours-and-roomier-week design.md D5).
              <h3
                className={`sticky top-0 z-10 flex items-center gap-2 bg-surface px-2.5 py-1.5 font-body text-[11px] uppercase tracking-wide ${
                  isBusy ? 'font-semibold text-text' : 'font-medium text-text-muted'
                }`}
              >
                <span className="shrink-0">{slotLabel(slot)}</span>
                <span aria-hidden className="h-px flex-1 bg-border" />
              </h3>
            ) : (
              <h3
                className={`sticky top-0 z-10 bg-surface/95 px-2 font-body text-[11px] uppercase tracking-wide backdrop-blur-sm ${
                  isBusy ? 'py-1.5 font-semibold text-text' : 'py-1 font-medium text-text-muted'
                }`}
              >
                {slotLabel(slot)}
              </h3>
            )}
            {isBusy ? (
              <ul className={`flex flex-col ${variant === 'block' ? 'gap-1.5 px-2 pb-2' : 'gap-2 px-1 pb-3'}`}>
                {group.map((event) => (
                  <li key={event.id}>
                    <CalendarEventChip
                      event={event}
                      boardBasePath={boardBasePath}
                      timezone={timezone}
                      showHostAndBranch={showHostAndBranch}
                      variant={variant}
                    />
                  </li>
                ))}
              </ul>
            ) : null}
            {index === timeline.frontier ? progress : null}
          </section>
        )
      })}
      {complete && total > 0 ? <DayListFooter loaded={events.length} total={total} status={status} onRetry={onLoadMore} /> : null}
    </div>
  )
}

function DayListFooter({ loaded, total, status, onRetry }: { loaded: number; total: number; status: DayPagesStatus; onRetry: () => void }) {
  return (
    <div role="status" className="flex flex-col items-center gap-1.5 px-2 py-3 font-body text-xs text-text-muted">
      {status === 'loading' ? <span>Loading more…</span> : null}
      {status === 'error' ? (
        <button type="button" onClick={onRetry} className="rounded-md border border-border bg-surface px-3 py-1 font-semibold text-text hover:bg-border-subtle">
          Couldn't load more · Retry
        </button>
      ) : null}
      <span className="tabular-nums">
        {loaded >= total ? `All ${total} ${total === 1 ? 'visit' : 'visits'}` : `Showing ${loaded} of ${total}`}
      </span>
    </div>
  )
}
