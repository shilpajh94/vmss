import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { useIsDesktop } from '../../../hooks/use-media-query'
import { isIsoDate, rangeFor, shiftDate, todayIn, type CalendarView, type DateRange } from '../../../utils/calendar-dates'
import { CALENDAR_STATUS_FILTERS, DEFAULT_CALENDAR_STATUSES } from '../calendar-status'

const VIEWS: readonly CalendarView[] = ['month', 'week', 'day']

function isView(value: string | null): value is CalendarView {
  return value !== null && (VIEWS as readonly string[]).includes(value)
}

export interface CalendarState {
  view: CalendarView
  date: string
  today: string
  range: DateRange
  branchId: string | undefined
  // Undefined means the API default (everything except denied).
  statuses: readonly string[] | undefined
  selectedStatuses: readonly string[]
  setView: (view: CalendarView) => void
  openDay: (date: string) => void
  goToday: () => void
  shift: (direction: 1 | -1) => void
  selectBranch: (branchId: string | undefined) => void
  toggleStatus: (status: string) => void
}

// The URL is the calendar's state (design.md W2): `view`, `date`, `branch`
// and a repeatable `status`. Writes replace the history entry, so Back from
// an opened invitation returns to exactly this view instead of stepping
// through every month the user paged past. `timezone` is the visit timezone
// from the last response — "today" follows it, not the browser.
export function useCalendarState(timezone: string | undefined): CalendarState {
  const [searchParams, setSearchParams] = useSearchParams()
  const isDesktop = useIsDesktop()

  const today = todayIn(timezone)
  const viewParam = searchParams.get('view')
  const view: CalendarView = isView(viewParam) ? viewParam : isDesktop ? 'month' : 'day'
  const dateParam = searchParams.get('date')
  const date = isIsoDate(dateParam) ? dateParam : today
  const branchId = searchParams.get('branch') || undefined
  const statusParams = searchParams.getAll('status')
  const statusKey = statusParams.join(',')
  const statuses = useMemo(() => {
    const known = statusKey.split(',').filter((status) => (CALENDAR_STATUS_FILTERS as readonly string[]).includes(status))
    return known.length > 0 ? known : undefined
  }, [statusKey])
  const range = useMemo(() => rangeFor(view, date), [view, date])

  const update = useCallback(
    (changes: Record<string, string | readonly string[] | undefined>) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          for (const [key, value] of Object.entries(changes)) {
            next.delete(key)
            if (value === undefined) continue
            if (typeof value === 'string') next.set(key, value)
            else value.forEach((item) => next.append(key, item))
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const toggleStatus = useCallback(
    (status: string) => {
      const current = statuses ?? DEFAULT_CALENDAR_STATUSES
      const next = current.includes(status) ? current.filter((item) => item !== status) : [...current, status]
      // Never filter down to nothing; back at the default, drop the param.
      if (next.length === 0) return
      const isDefault = next.length === DEFAULT_CALENDAR_STATUSES.length && DEFAULT_CALENDAR_STATUSES.every((item) => next.includes(item))
      update({ status: isDefault ? undefined : CALENDAR_STATUS_FILTERS.filter((item) => next.includes(item)) })
    },
    [statuses, update],
  )

  return {
    view,
    date,
    today,
    range,
    branchId,
    statuses,
    selectedStatuses: statuses ?? DEFAULT_CALENDAR_STATUSES,
    setView: useCallback((nextView: CalendarView) => update({ view: nextView }), [update]),
    openDay: useCallback((day: string) => update({ view: 'day', date: day }), [update]),
    goToday: useCallback(() => update({ date: undefined }), [update]),
    shift: useCallback((direction: 1 | -1) => update({ date: shiftDate(view, date, direction) }), [update, view, date]),
    selectBranch: useCallback((id: string | undefined) => update({ branch: id }), [update]),
    toggleStatus,
  }
}
