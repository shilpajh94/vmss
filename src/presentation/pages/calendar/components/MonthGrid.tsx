import { PRESS_FEEDBACK_CLASS } from '../../../components/ui/interactive'
import { dayOfMonth, formatShortDay, formatWeekday, isSameMonth } from '../../../utils/calendar-dates'
import { CalendarEventChip } from './CalendarEventChip'
import { eventsByDate } from './calendar-grouping'
import { busyTint } from '../calendar-status'
import type { BoardBasePath } from '../../../components/dashboard/dashboard-format'
import type { CalendarFeed } from '../../../../domain/entities/calendar-feed-schema'

// Chips per cell before "+N more"; on phones a cell shows only its count,
// whose tint steps up with the day's total (busyTint) on every screen size.
const CHIPS_PER_CELL = 3

interface MonthGridProps {
  feed: CalendarFeed
  anchorDate: string
  today: string
  boardBasePath: BoardBasePath
  onOpenDay: (date: string) => void
}

// Six full weeks. Each cell's number is the API's exact `days[].total`, so
// "+N more" stays right even when the event list was truncated.
export function MonthGrid({ feed, anchorDate, today, boardBasePath, onOpenDay }: MonthGridProps) {
  const byDate = eventsByDate(feed.events)
  const showHostAndBranch = feed.scope === 'branch'

  return (
    <div className="flex w-full flex-col overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="grid grid-cols-7 border-b border-border bg-border-subtle">
        {feed.days.slice(0, 7).map((day) => (
          <div key={day.date} className="px-2 py-2 text-center font-body text-xs font-semibold uppercase text-text-muted">
            {formatWeekday(day.date)}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {feed.days.map((day) => {
          const events = byDate.get(day.date) ?? []
          const shown = events.slice(0, CHIPS_PER_CELL)
          const more = day.total - shown.length
          const isToday = day.date === today
          const inMonth = isSameMonth(day.date, anchorDate)
          return (
            <div
              key={day.date}
              aria-label={`${formatShortDay(day.date)}: ${day.total} ${day.total === 1 ? 'visit' : 'visits'}`}
              className={`flex min-h-20 min-w-0 flex-col gap-1 border-b border-r border-border p-1 sm:min-h-28 sm:p-1.5 [&:nth-child(7n)]:border-r-0 ${
                inMonth ? '' : 'bg-border-subtle/60'
              }`}
            >
              <div className="flex items-center justify-between gap-1">
                <button
                  type="button"
                  onClick={() => onOpenDay(day.date)}
                  aria-label={`Open ${formatShortDay(day.date)}`}
                  aria-current={isToday ? 'date' : undefined}
                  className={`flex size-7 items-center justify-center rounded-full font-body text-xs font-semibold ${PRESS_FEEDBACK_CLASS} ${
                    isToday ? 'bg-admin-accent text-on-accent' : inMonth ? 'text-text hover:bg-border-subtle' : 'text-text-faint hover:bg-border-subtle'
                  }`}
                >
                  {dayOfMonth(day.date)}
                </button>
                {day.total > 0 ? (
                  <button
                    type="button"
                    onClick={() => onOpenDay(day.date)}
                    aria-hidden
                    tabIndex={-1}
                    className={`min-w-6 rounded-full px-1.5 text-center font-body text-[11px] font-bold text-text tabular-nums ${busyTint(day.total)}`}
                    title={`${day.total} ${day.total === 1 ? 'visit' : 'visits'}`}
                  >
                    {day.total}
                  </button>
                ) : null}
              </div>
              <div className="hidden min-w-0 flex-col gap-0.5 sm:flex">
                {shown.map((event) => (
                  <CalendarEventChip
                    key={event.id}
                    event={event}
                    boardBasePath={boardBasePath}
                    timezone={feed.timezone}
                    showHostAndBranch={showHostAndBranch}
                    variant="compact"
                  />
                ))}
                {more > 0 ? (
                  <button
                    type="button"
                    onClick={() => onOpenDay(day.date)}
                    className="self-start rounded px-1.5 font-body text-xs font-semibold text-admin-accent hover:underline"
                  >
                    +{more} more
                  </button>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
