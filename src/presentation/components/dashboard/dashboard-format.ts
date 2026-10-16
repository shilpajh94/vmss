// Formatting helpers shared by the dashboard cards and charts.

const DAY_LABEL = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })
const LONG_DATE_LABEL = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' })

// A plain calendar date from the API ("2026-10-16") as a local Date, so it is
// never shifted a day by UTC parsing.
export function parseCalendarDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function formatDayLabel(value: string): string {
  return DAY_LABEL.format(parseCalendarDate(value))
}

// The server's "today" in the tenant's timezone (dashboard-insights "Every
// Dashboard Figure Comes From the Live API") — never the browser's clock.
export function formatLongDate(value: string): string {
  return LONG_DATE_LABEL.format(parseCalendarDate(value))
}

export function formatHour(hour: number): string {
  const suffix = hour < 12 ? 'am' : 'pm'
  const twelveHour = hour % 12 === 0 ? 12 : hour % 12
  return `${twelveHour}${suffix}`
}

// The current hour of day in `timeZone`, falling back to the browser's.
export function currentHourIn(timeZone: string | undefined): number {
  try {
    const hour = new Intl.DateTimeFormat('en-US', { hour: 'numeric', hourCycle: 'h23', timeZone }).format(new Date())
    return Number(hour) % 24
  } catch {
    return new Date().getHours()
  }
}

export function greetingForHour(hour: number): string {
  if (hour < 12) return 'Good Morning'
  if (hour < 18) return 'Good Afternoon'
  return 'Good Evening'
}

// "12 min", "2 h", "3 d" — how long the oldest pending request has waited.
export function formatWaitingSince(isoTimestamp: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(isoTimestamp).getTime()) / 60_000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} h`
  return `${Math.floor(hours / 24)} d`
}

// The scheduled visit as a local date-time string ("2026-10-22T14:00:00"),
// joined without a zone so it parses as local time.
export function scheduledLocal(date: string | null, time: string | null): string | null {
  if (!date) return null
  return `${date}T${time ?? '00:00:00'}`
}

// Board labels, so a status reads the same on the dashboard and the board.
export const STATUS_LABELS: Record<string, string> = {
  submitted: 'Requested',
  approved: 'Approved',
  checked_in: 'Checked-in',
  checked_out: 'Checked-out',
  denied: 'Denied',
  archived: 'Archived',
}

// Where a dashboard link lands: admins on the admin board, everyone else
// (reception, hosts) on the staff board.
export type BoardBasePath = '/admin/invitations' | '/staff/invitations'

export function boardStatusPath(basePath: BoardBasePath, status: string): string {
  return `${basePath}?status=${encodeURIComponent(status)}`
}

export function boardInvitationPath(basePath: BoardBasePath, invitationId: string): string {
  return `${basePath}?invitationId=${encodeURIComponent(invitationId)}`
}
