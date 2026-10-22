import type { CalendarEvent, CalendarFeed } from '../../domain/entities/calendar-feed-schema'

// `from`/`to` are inclusive `YYYY-MM-DD` dates. `branchId` narrows a
// branch-wide feed to one branch (sent as `X-Branch-ID`); `statuses` omitted
// means the API default (everything except denied).
export interface CalendarFeedQuery {
  from: string
  to: string
  branchId?: string
  statuses?: readonly string[]
  // Only each day's first N events (the rest are paged per day).
  perDayLimit?: number
}

export interface CalendarDayPageQuery {
  date: string
  page: number
  pageSize: number
  branchId?: string
  statuses?: readonly string[]
}

export interface CalendarDayPage {
  events: CalendarEvent[]
  // Every matching event of the day, not just this page.
  total: number
}

export interface CalendarRepository {
  getFeed(query: CalendarFeedQuery): Promise<CalendarFeed>
  getDayPage(query: CalendarDayPageQuery): Promise<CalendarDayPage>
}
