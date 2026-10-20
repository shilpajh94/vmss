// Calendar wording and colour for each invitation status (add-staff-calendar
// design.md D8; add-calendar-colours-and-theme-modes design.md D8). Events
// are filled with their status tint; text on a fill is body text, since a
// status-coloured label on its own tint fails contrast (measured in that
// design). Full class names are spelled out so Tailwind generates them.
interface CalendarStatusStyle {
  label: string
  // Status tint behind an event or an enabled filter chip.
  fillClass: string
  // Solid status marker.
  dotClass: string
}

const CALENDAR_STATUS_STYLES: Record<string, CalendarStatusStyle> = {
  submitted: { label: 'Pending', fillClass: 'bg-info/15 dark:bg-info/25', dotClass: 'bg-info' },
  approved: { label: 'Expected', fillClass: 'bg-success/15 dark:bg-success/25', dotClass: 'bg-success' },
  checked_in: { label: 'Inside', fillClass: 'bg-secondary-accent/15 dark:bg-secondary-accent/25', dotClass: 'bg-secondary-accent' },
  checked_out: { label: 'Visited', fillClass: 'bg-neutral-subtle', dotClass: 'bg-text-faint' },
  archived: { label: 'Missed', fillClass: 'bg-warning/15 dark:bg-warning/25', dotClass: 'bg-warning' },
  denied: { label: 'Denied', fillClass: 'bg-danger/15 dark:bg-danger/25', dotClass: 'bg-danger' },
}

const FALLBACK_STYLE: CalendarStatusStyle = { label: 'Other', fillClass: 'bg-neutral-subtle', dotClass: 'bg-text-faint' }

export function calendarStatusStyle(status: string): CalendarStatusStyle {
  return CALENDAR_STATUS_STYLES[status] ?? FALLBACK_STYLE
}

// How busy a day is, for the month view's count badge (staff-calendar
// "Busy day stands out"): none / light 1-4 / medium 5-14 / strong 15+.
export function busyTint(total: number): string {
  if (total <= 0) return ''
  if (total < 5) return 'bg-admin-accent/10'
  if (total < 15) return 'bg-admin-accent/25'
  return 'bg-admin-accent/45'
}

// Filter choices, in lifecycle order. The API default is all but `denied`.
export const CALENDAR_STATUS_FILTERS = ['submitted', 'approved', 'checked_in', 'checked_out', 'archived', 'denied'] as const
export const DEFAULT_CALENDAR_STATUSES: readonly string[] = CALENDAR_STATUS_FILTERS.filter((status) => status !== 'denied')

// Visits per day the feed returns for each view — all a month cell shows,
// a week column's first page, a day's first page — and the page size each
// then loads more by (improve-calendar-scale-and-theme-switch design.md W2).
export const PER_DAY_LIMIT = { month: 3, week: 10, day: 20 } as const

