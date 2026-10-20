import { useRef, type RefObject } from 'react'
import { useIsDesktop } from '../../../hooks/use-media-query'
import { formatPeriodTitle } from '../../../utils/calendar-dates'
import { DayListStatus, PagedDayList } from './PagedDayList'
import { useDayPages } from '../hooks/use-day-pages'
import { useFillHeight } from '../hooks/use-fill-height'
import { PER_DAY_LIMIT } from '../calendar-status'
import type { BoardBasePath } from '../../../components/dashboard/dashboard-format'
import type { CalendarFeed } from '../../../../domain/entities/calendar-feed-schema'

// Same floor as the Week board from `lg` up (fix-paging-footers-and-calendar-day-scroll design.md D3).
const DAY_CARD_FLOOR = 240

interface DayAgendaProps {
  feed: CalendarFeed
  branchId: string | undefined
  statuses: readonly string[] | undefined
  boardBasePath: BoardBasePath
  /** The page header and toolbar above the card; see useFillHeight. */
  controlsRef: RefObject<HTMLElement | null>
}

// One day's visits with full details on the working-hours timeline,
// "No visits" above it on an empty day. Starts from the feed's first 20 (it
// is requested with perDayLimit 20 for a one-day range) and loads 20 more as
// the list scrolls near the last loaded visit, until the whole day is shown
// (staff-calendar "Month, week and day views": Day).
//
// From `lg` up the card fills the page below the toolbar and only its body
// scrolls, between a fixed date/count header and a fixed paging footer
// (staff-calendar "Day view scrolls its timeline inside its own panel").
// Below `lg` it grows with its content and the page scrolls, so lazy
// loading watches <main> there instead of the card's body
// (fix-paging-footers-and-calendar-day-scroll design.md D5).
export function DayAgenda({ feed, branchId, statuses, boardBasePath, controlsRef }: DayAgendaProps) {
  const day = feed.days[0]
  const pages = useDayPages({
    date: day.date,
    branchId,
    statuses,
    pageSize: PER_DAY_LIMIT.day,
    seedEvents: feed.events,
    seedTotal: day.total,
  })
  const isDesktop = useIsDesktop()
  const [cardRef, height] = useFillHeight<HTMLDivElement>({ floor: DAY_CARD_FLOOR, enabled: isDesktop, observeRef: controlsRef })
  const bodyRef = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={cardRef}
      style={height === undefined ? undefined : { height }}
      className="flex w-full shrink-0 flex-col rounded-2xl border border-border bg-surface lg:overflow-hidden"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 rounded-t-2xl border-b border-border bg-border-subtle/60 px-3 py-2 font-body md:px-4">
        <p className="text-sm font-semibold text-text">{formatPeriodTitle('day', day.date)}</p>
        <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-semibold tabular-nums text-text-muted">
          {pages.total} {pages.total === 1 ? 'visit' : 'visits'}
        </span>
      </div>
      {/* No top padding: the sticky hour headings pin to the scroll area's
          top edge, and padding there would show visits above them. */}
      <div ref={bodyRef} data-day-body className="scrollbar-autohide min-h-0 flex-1 px-2 pb-2 md:px-3 md:pb-3 lg:overflow-y-auto lg:overscroll-contain">
        <PagedDayList
          events={pages.events}
          total={pages.total}
          status={pages.status}
          onLoadMore={pages.loadMore}
          scrollRootRef={isDesktop ? bodyRef : undefined}
          boardBasePath={boardBasePath}
          timezone={feed.timezone}
          showHostAndBranch={feed.scope === 'branch'}
          variant="detail"
        />
      </div>
      {pages.total > 0 ? (
        <div className="shrink-0 border-t border-border">
          <DayListStatus loaded={pages.events.length} total={pages.total} status={pages.status} onRetry={pages.loadMore} />
        </div>
      ) : null}
    </div>
  )
}
