import { useNavigate } from 'react-router'
import { PRESS_FEEDBACK_CLASS } from '../../../components/ui/interactive'
import { boardInvitationPath, type BoardBasePath } from '../../../components/dashboard/dashboard-format'
import { formatInstantTime, formatScheduledTime } from '../../../utils/calendar-dates'
import { calendarStatusStyle } from '../calendar-status'
import type { CalendarEvent } from '../../../../domain/entities/calendar-feed-schema'

// Visitor-category badge colour as a left accent, mirroring the category
// table's swatches.
const CATEGORY_ACCENT: Record<string, string> = {
  blue: 'border-l-info',
  orange: 'border-l-warning',
  gold: 'border-l-vip',
  grey: 'border-l-text-muted',
}

interface CalendarEventChipProps {
  event: CalendarEvent
  boardBasePath: BoardBasePath
  timezone: string
  // Branch-wide viewers also see host and branch (design.md D8).
  showHostAndBranch: boolean
  // 'compact' for month cells, 'block' for week columns, 'detail' for the day list.
  variant: 'compact' | 'block' | 'detail'
}

export function visitorLabel(event: CalendarEvent): string {
  const extra = event.visitorCount - 1
  return extra > 0 ? `${event.primaryContactFullName} +${extra}` : event.primaryContactFullName
}

function scheduledLabel(event: CalendarEvent): string {
  return event.time ? formatScheduledTime(event.time) : 'Any time'
}

function hostLabel(event: CalendarEvent): string {
  return event.hostFullName ?? 'Unassigned'
}

// One visit. Activating it opens the existing invitation detail modal via the
// board's deep link (design.md D7); a <button> so Space works as well as Enter.
export function CalendarEventChip({ event, boardBasePath, timezone, showHostAndBranch, variant }: CalendarEventChipProps) {
  const navigate = useNavigate()
  const status = calendarStatusStyle(event.status)
  const accent = CATEGORY_ACCENT[event.visitorCategoryBadgeColor ?? ''] ?? 'border-l-border'
  const open = () => navigate(boardInvitationPath(boardBasePath, event.id))

  const summary = [
    `${scheduledLabel(event)} · ${visitorLabel(event)}`,
    status.label,
    event.purposeOfVisit,
    showHostAndBranch ? `Host: ${hostLabel(event)}` : null,
    showHostAndBranch ? event.branchName : null,
  ]
    .filter(Boolean)
    .join(' · ')

  // Filled with the status tint; everything on it is body text (a muted or
  // status-coloured label on the tint fails contrast — design.md D8).
  const fill = `${status.fillClass} border-l-[3px] ${accent} text-text hover:ring-1 hover:ring-text/25 ${PRESS_FEEDBACK_CLASS}`
  const dot = <span aria-hidden className={`size-2 shrink-0 rounded-full ${status.dotClass}`} />

  if (variant === 'compact') {
    return (
      <button
        type="button"
        onClick={open}
        title={summary}
        aria-label={summary}
        className={`flex w-full min-w-0 items-center gap-1.5 rounded px-1.5 py-0.5 text-left font-body text-xs ${fill}`}
      >
        {dot}
        {event.time ? <span className="shrink-0 tabular-nums">{formatScheduledTime(event.time)}</span> : null}
        <span className="truncate font-semibold">{visitorLabel(event)}</span>
      </button>
    )
  }

  if (variant === 'block') {
    return (
      <button
        type="button"
        onClick={open}
        title={summary}
        aria-label={summary}
        className={`flex w-full min-w-0 flex-col gap-0.5 rounded-lg px-2.5 py-2 text-left font-body ${fill}`}
      >
        <span className="truncate text-[13px] font-semibold">{visitorLabel(event)}</span>
        {/* Two lines only: the status is the fill and the dot here, and its
            word stays in the title and accessible name (staff-calendar
            "Events show schedule, status and visitor at a glance";
            calendar-working-hours-and-roomier-week design.md D4). */}
        <span className="flex min-w-0 items-center gap-1.5 text-xs">
          {dot}
          <span className="truncate">
            <span className="tabular-nums">{scheduledLabel(event)}</span>
            {showHostAndBranch ? ` · ${hostLabel(event)}` : ''}
          </span>
        </span>
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={open}
      aria-label={summary}
      className={`flex w-full min-w-0 flex-col gap-2 rounded-xl p-3 text-left font-body sm:flex-row sm:items-start sm:justify-between ${fill}`}
    >
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-sm font-semibold">{visitorLabel(event)}</span>
        <span className="text-xs">
          <span className="font-semibold">{scheduledLabel(event)}</span>
          {event.expectedDuration ? ` · ${event.expectedDuration}` : ''}
          {event.purposeOfVisit ? ` · ${event.purposeOfVisit}` : ''}
        </span>
        {showHostAndBranch ? (
          <span className="text-xs">
            Host: {hostLabel(event)}
            {event.branchName ? ` · ${event.branchName}` : ''}
            {event.buildingName ? ` · ${event.buildingName}` : ''}
          </span>
        ) : null}
        {event.checkedInAt || event.checkedOutAt ? (
          <span className="text-xs">
            {event.checkedInAt ? `Checked in ${formatInstantTime(event.checkedInAt, timezone)}` : ''}
            {event.checkedInAt && event.checkedOutAt ? ' · ' : ''}
            {event.checkedOutAt ? `Checked out ${formatInstantTime(event.checkedOutAt, timezone)}` : ''}
          </span>
        ) : null}
      </span>
      <span className="flex shrink-0 items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold">
          {dot}
          {status.label}
        </span>
        <span className="font-mono text-xs">{event.trackingId}</span>
      </span>
    </button>
  )
}
