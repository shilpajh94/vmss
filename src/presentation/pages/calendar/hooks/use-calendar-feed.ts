import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useLiveDashboard, useLiveResource } from '../../../hooks/use-live-dashboard'
import type { CalendarFeed } from '../../../../domain/entities/calendar-feed-schema'
import type { DateRange } from '../../../utils/calendar-dates'

const LOAD_ERROR = 'Something went wrong loading the calendar. Please try again.'

interface UseCalendarFeedOptions {
  range: DateRange
  branchId: string | undefined
  statuses: readonly string[] | undefined
  // Each day's first N visits only; the rest are paged per day.
  perDayLimit: number
  loginPath: string
}

interface KeyedFeed {
  key: string
  feed: CalendarFeed
}

// The calendar feed for the visible range, kept live like the dashboards
// (polling, refetch on return and on invitation activity, the top-bar
// refresh control) via the shared live-resource hooks (design.md W4). Each
// response is tagged with the query it answers, so while a new month,
// branch or filter loads, the previous one is shown as stale — never as if it
// were the new one.
export function useCalendarFeed({ range, branchId, statuses, perDayLimit, loginPath }: UseCalendarFeedOptions) {
  const navigate = useNavigate()
  const { getCalendarFeedUseCase } = useAppDependencies()

  useEffect(() => {
    if (!sessionStorage.getItem('token')) navigate(loginPath, { replace: true })
  }, [navigate, loginPath])

  const key = `${range.from}:${range.to}:${branchId ?? 'all'}:${statuses?.join(',') ?? 'default'}:${perDayLimit}`
  const resource = useLiveResource<KeyedFeed>(
    async () => ({ key, feed: await getCalendarFeedUseCase.execute({ from: range.from, to: range.to, branchId, statuses, perDayLimit }) }),
    key,
    true,
  )
  const live = useLiveDashboard([resource], LOAD_ERROR, true)

  const isStale = resource.data !== undefined && resource.data.key !== key
  return {
    feed: resource.data?.feed,
    isStale,
    // A newly chosen view/branch/filter failed (e.g. a 403 branch): there's
    // nothing current to show, so the page shows the error, not old data.
    hasCurrentError: resource.hasError && (resource.data === undefined || isStale),
    ...live,
  }
}
