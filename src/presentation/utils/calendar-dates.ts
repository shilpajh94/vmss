import { todayAsDateInputValue } from './local-date-input-value'

// Calendar date math on plain `YYYY-MM-DD` strings (add-staff-calendar
// design.md W3). Every calculation runs on UTC midnights, so the browser's
// own timezone and DST changes can never shift a day; the visit timezone
// only enters through `todayIn`.

export type CalendarView = 'month' | 'week' | 'day'

export interface DateRange {
  from: string
  to: string
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const DAY_MS = 86_400_000

function toUtc(date: string): Date {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

function fromUtc(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export function isIsoDate(value: string | null | undefined): value is string {
  return typeof value === 'string' && ISO_DATE.test(value) && fromUtc(toUtc(value)) === value
}

export function addDays(date: string, days: number): string {
  return fromUtc(new Date(toUtc(date).getTime() + days * DAY_MS))
}

function addMonths(date: string, months: number): string {
  const current = toUtc(date)
  return fromUtc(new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() + months, 1)))
}

// Weeks start on Monday (design.md D6).
export function startOfWeek(date: string): string {
  const mondayOffset = (toUtc(date).getUTCDay() + 6) % 7
  return addDays(date, -mondayOffset)
}

function startOfMonth(date: string): string {
  return `${date.slice(0, 7)}-01`
}

// Six full weeks (42 days) from the Monday on or before the 1st — the API's
// maximum range, so a month grid is always one request.
export function monthGridRange(date: string): DateRange {
  const from = startOfWeek(startOfMonth(date))
  return { from, to: addDays(from, 41) }
}

export function rangeFor(view: CalendarView, date: string): DateRange {
  if (view === 'month') return monthGridRange(date)
  if (view === 'week') {
    const from = startOfWeek(date)
    return { from, to: addDays(from, 6) }
  }
  return { from: date, to: date }
}

export function datesIn({ from, to }: DateRange): string[] {
  const days: string[] = []
  for (let day = from; day <= to; day = addDays(day, 1)) days.push(day)
  return days
}

export function shiftDate(view: CalendarView, date: string, direction: 1 | -1): string {
  if (view === 'month') return addMonths(date, direction)
  return addDays(date, view === 'week' ? 7 * direction : direction)
}

export function isSameMonth(date: string, anchor: string): boolean {
  return date.slice(0, 7) === anchor.slice(0, 7)
}

// Today's date in `timezone` (the visit timezone the API reports). Falls
// back to the browser's date before the first response arrives, or if the
// zone name is not one this browser knows.
export function todayIn(timezone: string | undefined): string {
  if (!timezone) return todayAsDateInputValue()
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  } catch {
    return todayAsDateInputValue()
  }
}

const MONTH_TITLE = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const DAY_TITLE = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const SHORT_DAY = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const WEEKDAY = new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: 'UTC' })
const CLOCK = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'UTC' })

export function formatPeriodTitle(view: CalendarView, date: string): string {
  if (view === 'month') return MONTH_TITLE.format(toUtc(date))
  if (view === 'day') return DAY_TITLE.format(toUtc(date))
  const { from, to } = rangeFor('week', date)
  return `${SHORT_DAY.format(toUtc(from))} – ${SHORT_DAY.format(toUtc(to))} ${to.slice(0, 4)}`
}

export function formatWeekday(date: string): string {
  return WEEKDAY.format(toUtc(date))
}

export function formatShortDay(date: string): string {
  return SHORT_DAY.format(toUtc(date))
}

export function dayOfMonth(date: string): number {
  return Number(date.slice(8, 10))
}

// "09:30:00" → "9:30 AM". A scheduled time is a wall-clock time with no
// zone, so it is formatted as-is rather than converted.
export function formatScheduledTime(time: string): string {
  const [hours, minutes] = time.split(':').map(Number)
  return CLOCK.format(new Date(Date.UTC(1970, 0, 1, hours, minutes)))
}

export function hourOf(time: string): number {
  return Number(time.slice(0, 2))
}

export function formatHour(hour: number): string {
  return CLOCK.format(new Date(Date.UTC(1970, 0, 1, hour, 0)))
}

// An actual check-in/out instant shown in the visit timezone.
export function formatInstantTime(iso: string, timezone: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: timezone }).format(new Date(iso))
  } catch {
    return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(iso))
  }
}
