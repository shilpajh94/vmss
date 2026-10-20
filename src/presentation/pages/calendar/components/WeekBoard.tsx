import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { PRESS_FEEDBACK_CLASS } from '../../../components/ui/interactive'
import { useIsDesktop } from '../../../hooks/use-media-query'
import { dayOfMonth, formatShortDay, formatWeekday } from '../../../utils/calendar-dates'
import { DayListStatus, PagedDayList } from './PagedDayList'
import { eventsByDate } from './calendar-grouping'
import { useDayPages } from '../hooks/use-day-pages'
import { useFillHeight } from '../hooks/use-fill-height'
import { PER_DAY_LIMIT } from '../calendar-status'
import type { BoardBasePath } from '../../../components/dashboard/dashboard-format'
import type { CalendarDay, CalendarEvent, CalendarFeed } from '../../../../domain/entities/calendar-feed-schema'

const NO_EVENTS: CalendarEvent[] = []
// The board's height floor: from `lg` up it still fits a 720px-tall laptop
// window (header, footer and about four hours per column); below `lg` the
// page scrolls as a whole anyway (staff-calendar "Week board fits short
// desktop windows").
const DESKTOP_BOARD_FLOOR = 240
const MOBILE_BOARD_FLOOR = 420

interface WeekBoardProps {
  feed: CalendarFeed
  today: string
  branchId: string | undefined
  statuses: readonly string[] | undefined
  boardBasePath: BoardBasePath
  onOpenDay: (date: string) => void
  /** The page header and toolbar above the board; see useFillHeight. */
  controlsRef: RefObject<HTMLElement | null>
  /** Changes when something else above the board comes or goes. */
  remeasureKey: unknown
}

// Seven day columns that each scroll on their own, inside a board that
// fits the screen; sideways snap scrolling below 2xl (1/2/3/5/7 columns per
// screen) (staff-calendar "Month, week and day views with a working-hours
// timeline": Week; calendar-working-hours-and-roomier-week design.md D3).
// Its height is the space left below the toolbar, measured at every width
// (fix-paging-footers-and-calendar-day-scroll design.md D3).
export function WeekBoard({ feed, today, branchId, statuses, boardBasePath, onOpenDay, controlsRef, remeasureKey }: WeekBoardProps) {
  const isDesktop = useIsDesktop()
  const [boardRef, height] = useFillHeight<HTMLDivElement>({
    floor: isDesktop ? DESKTOP_BOARD_FLOOR : MOBILE_BOARD_FLOOR,
    enabled: true,
    observeRef: controlsRef,
    remeasureKey,
  })
  // Grouped once per feed, so each column's seed only changes on a refresh.
  const byDate = useMemo(() => eventsByDate(feed.events), [feed])

  // Where fewer than seven columns fit, open the current week at today's
  // column; the browser clamps at the week's end. Keyed on the week, so a
  // refresh never moves the board (staff-calendar "Calendar is usable on
  // small screens"; calendar-working-hours-and-roomier-week design.md D3).
  const weekStart = feed.days[0]?.date
  useLayoutEffect(() => {
    const board = boardRef.current
    if (!board) return
    const column = board.querySelector<HTMLElement>('[data-today]')
    board.scrollLeft = column ? board.scrollLeft + column.getBoundingClientRect().left - board.getBoundingClientRect().left - board.clientLeft : 0
  }, [weekStart, boardRef])

  return (
    <div
      ref={boardRef}
      style={{ height }}
      className="flex w-full shrink-0 snap-x snap-mandatory overflow-x-auto overflow-y-hidden overscroll-x-contain rounded-2xl border border-border bg-surface"
    >
      {feed.days.map((day) => (
        <DayColumn
          key={day.date}
          day={day}
          seedEvents={byDate.get(day.date) ?? NO_EVENTS}
          isToday={day.date === today}
          feed={feed}
          branchId={branchId}
          statuses={statuses}
          boardBasePath={boardBasePath}
          onOpenDay={onOpenDay}
        />
      ))}
    </div>
  )
}

interface DayColumnProps {
  day: CalendarDay
  seedEvents: CalendarEvent[]
  isToday: boolean
  feed: CalendarFeed
  branchId: string | undefined
  statuses: readonly string[] | undefined
  boardBasePath: BoardBasePath
  onOpenDay: (date: string) => void
}

function DayColumn({ day, seedEvents, isToday, feed, branchId, statuses, boardBasePath, onOpenDay }: DayColumnProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const pages = useDayPages({
    date: day.date,
    branchId,
    statuses,
    pageSize: PER_DAY_LIMIT.week,
    seedEvents,
    seedTotal: day.total,
  })

  return (
    <section
      aria-label={`${formatShortDay(day.date)}: ${pages.total} ${pages.total === 1 ? 'visit' : 'visits'}`}
      data-today={isToday || undefined}
      className="flex h-full w-full shrink-0 snap-start flex-col border-r border-border last:border-r-0 sm:w-1/2 md:w-1/3 xl:w-1/5 2xl:w-[calc(100%/7)]"
    >
      <button
        type="button"
        onClick={() => onOpenDay(day.date)}
        aria-current={isToday ? 'date' : undefined}
        aria-label={`Open ${formatShortDay(day.date)}: ${pages.total} ${pages.total === 1 ? 'visit' : 'visits'}`}
        className={`flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2 font-body hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS} ${
          isToday ? 'bg-admin-accent/10' : 'bg-border-subtle/60'
        }`}
      >
        <span className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">{formatWeekday(day.date)}</span>
          <span
            className={`flex size-7 items-center justify-center rounded-full text-sm font-semibold tabular-nums ${
              isToday ? 'bg-admin-accent text-on-accent' : 'text-text'
            }`}
          >
            {dayOfMonth(day.date)}
          </span>
        </span>
        <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-semibold tabular-nums text-text-muted">{pages.total}</span>
      </button>
      <div ref={bodyRef} className="scrollbar-autohide min-h-0 flex-1 overflow-y-auto overscroll-contain pt-1">
        <PagedDayList
          events={pages.events}
          total={pages.total}
          status={pages.status}
          onLoadMore={pages.loadMore}
          scrollRootRef={bodyRef}
          boardBasePath={boardBasePath}
          timezone={feed.timezone}
          showHostAndBranch={feed.scope === 'branch'}
          variant="block"
        />
      </div>
      {pages.total > 0 ? (
        <div className="shrink-0 border-t border-border">
          <DayListStatus loaded={pages.events.length} total={pages.total} status={pages.status} onRetry={pages.loadMore} />
        </div>
      ) : null}
    </section>
  )
}
