import { PagedDayList } from './PagedDayList'
import { useDayPages } from '../hooks/use-day-pages'
import { PER_DAY_LIMIT } from '../calendar-status'
import type { BoardBasePath } from '../../../components/dashboard/dashboard-format'
import type { CalendarFeed } from '../../../../domain/entities/calendar-feed-schema'

interface DayAgendaProps {
  feed: CalendarFeed
  branchId: string | undefined
  statuses: readonly string[] | undefined
  boardBasePath: BoardBasePath
}

// One day's visits with full details on the working-hours timeline,
// "No visits" above it on an empty day. Starts from the feed's first 20 (it
// is requested with perDayLimit 20 for a one-day range) and loads 20 more as
// the page scrolls near the last loaded visit, until the whole day is shown
// (staff-calendar "Month, week and day views": Day).
export function DayAgenda({ feed, branchId, statuses, boardBasePath }: DayAgendaProps) {
  const day = feed.days[0]
  const pages = useDayPages({
    date: day.date,
    branchId,
    statuses,
    pageSize: PER_DAY_LIMIT.day,
    seedEvents: feed.events,
    seedTotal: day.total,
  })

  return (
    <div className="w-full rounded-2xl border border-border bg-surface p-2 md:p-3">
      <PagedDayList
        events={pages.events}
        total={pages.total}
        status={pages.status}
        onLoadMore={pages.loadMore}
        boardBasePath={boardBasePath}
        timezone={feed.timezone}
        showHostAndBranch={feed.scope === 'branch'}
        variant="detail"
      />
    </div>
  )
}
