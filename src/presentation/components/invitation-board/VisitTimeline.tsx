import type { ComponentType, SVGProps } from 'react'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { Skeleton } from '../ui/Skeleton'
import {
  AlertCircleIcon,
  BellIcon,
  CameraIcon,
  CheckIcon,
  CircleDotIcon,
  ClockIcon,
  IdCardIcon,
  LogOutIcon,
  MailIcon,
  RefreshCcwIcon,
  TagIcon,
  UndoIcon,
  UserCheckIcon,
  XIcon,
} from '../icons'
import { formatDate, formatTime } from '../../utils/format-time'
import { useVisitTimeline } from '../../hooks/use-visit-timeline'
import type { VisitTimelineEvent } from '../../../domain/entities/visit-timeline-schema'

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>

interface EventStyle {
  label: string
  Icon: IconComponent
  toneClass: string
}

const EVENT_STYLES: Record<string, EventStyle> = {
  invited: { label: 'Invited', Icon: MailIcon, toneClass: 'bg-info/10 text-info' },
  approved: { label: 'Approved', Icon: CheckIcon, toneClass: 'bg-success/10 text-success-text' },
  denied: { label: 'Denied', Icon: XIcon, toneClass: 'bg-danger/10 text-danger' },
  approval_reverted: { label: 'Approval reverted', Icon: UndoIcon, toneClass: 'bg-warning/10 text-warning' },
  id_verified: { label: 'ID verified', Icon: IdCardIcon, toneClass: 'bg-success/10 text-success-text' },
  photo_captured: { label: 'Photo captured', Icon: CameraIcon, toneClass: 'bg-info/10 text-info' },
  checked_in: { label: 'Checked in', Icon: UserCheckIcon, toneClass: 'bg-secondary-accent/10 text-secondary-accent' },
  checked_out: { label: 'Checked out', Icon: LogOutIcon, toneClass: 'bg-text-faint/15 text-text-muted' },
  badge_printed: { label: 'Badge printed', Icon: TagIcon, toneClass: 'bg-info/10 text-info' },
  badge_reprinted: { label: 'Badge reprinted', Icon: RefreshCcwIcon, toneClass: 'bg-warning/10 text-warning' },
  notification_sent: { label: 'Notification sent', Icon: BellIcon, toneClass: 'bg-secondary-accent/10 text-secondary-accent' },
}

// An event type this build doesn't know (the API adds them over time) is a
// generic event rather than an error.
const GENERIC_STYLE: EventStyle = { label: 'Event', Icon: CircleDotIcon, toneClass: 'bg-neutral-subtle text-text-muted' }

function dayKey(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? 'unknown' : `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

function dayLabel(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (dayKey(iso) === dayKey(today.toISOString())) return 'Today'
  if (dayKey(iso) === dayKey(yesterday.toISOString())) return 'Yesterday'
  return formatDate(iso)
}

// Consecutive events on the same calendar day share one heading; the list
// keeps the API's order, so this works for either sort direction.
function groupByDay(events: VisitTimelineEvent[]): { key: string; label: string; events: VisitTimelineEvent[] }[] {
  const groups: { key: string; label: string; events: VisitTimelineEvent[] }[] = []
  for (const event of events) {
    const key = dayKey(event.occurredAt)
    const last = groups[groups.length - 1]
    if (last && last.key === key) last.events.push(event)
    else groups.push({ key, label: dayLabel(event.occurredAt), events: [event] })
  }
  return groups
}

const DATE_INPUT_CLASS =
  'min-h-9 w-full rounded-lg border border-border-subtle bg-surface px-2 font-body text-[12px] text-text focus-visible:ring-2 focus-visible:ring-secondary-accent focus-visible:outline-none'

function TimelineSkeleton() {
  return (
    <div role="status" aria-label="Loading timeline…" aria-busy="true" className="flex flex-col gap-4 rounded-xl border border-border-subtle p-4">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="flex items-start gap-3">
          <Skeleton className="size-8 shrink-0 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        </div>
      ))}
    </div>
  )
}

interface VisitLocationItem {
  label: string
  value?: string | null
}

/** The audit-backed event history of one invitation, shown in its own dialog
 * for users holding `timeline:view`. */
export function VisitTimeline({ invitationId, visitLocation = [] }: { invitationId: string; visitLocation?: VisitLocationItem[] }) {
  const timeline = useVisitTimeline(invitationId, true)
  const { events, isLoading, error, hasMore } = timeline
  const hasFilters = Boolean(timeline.occurredAfter || timeline.occurredBefore)
  const groups = groupByDay(events)
  const shownLocation = visitLocation.filter((item) => item.value)

  return (
    <div className="flex flex-col gap-4">
      {shownLocation.length > 0 ? (
        <div className="grid grid-cols-1 gap-x-4 gap-y-3 rounded-xl border border-border-subtle p-3 sm:grid-cols-2">
          {shownLocation.map((item) => (
            <div key={item.label} className="flex min-w-0 flex-col gap-0.5">
              <span className="text-overline text-text-faint">{item.label}</span>
              <span className="truncate font-body text-[13px] font-medium text-text">{item.value}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="flex flex-col gap-3 rounded-xl border border-border-subtle bg-surface-inset p-3 sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-overline text-text-faint">From</span>
          <input
            type="datetime-local"
            className={DATE_INPUT_CLASS}
            value={timeline.occurredAfter}
            max={timeline.occurredBefore || undefined}
            onChange={(event) => timeline.setOccurredAfter(event.target.value)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-overline text-text-faint">To</span>
          <input
            type="datetime-local"
            className={DATE_INPUT_CLASS}
            value={timeline.occurredBefore}
            min={timeline.occurredAfter || undefined}
            onChange={(event) => timeline.setOccurredBefore(event.target.value)}
          />
        </label>
        <div className="flex gap-2">
          {hasFilters ? (
            <button
              type="button"
              onClick={() => {
                timeline.setOccurredAfter('')
                timeline.setOccurredBefore('')
              }}
              className="min-h-9 rounded-lg px-3 font-body text-[12px] font-semibold text-text-muted hover:text-text"
            >
              Clear
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => timeline.setSortOrder(timeline.sortOrder === 'desc' ? 'asc' : 'desc')}
            className="min-h-9 whitespace-nowrap rounded-lg border border-border-subtle bg-surface px-3 font-body text-[12px] font-semibold text-text-muted hover:text-text"
          >
            {timeline.sortOrder === 'desc' ? 'Newest first' : 'Oldest first'}
          </button>
        </div>
      </div>

      {isLoading && events.length === 0 && !error ? (
        <TimelineSkeleton />
      ) : error && events.length === 0 ? (
        <ErrorState message={error} onRetry={timeline.retry} className="p-4 md:p-6" />
      ) : events.length === 0 ? (
        <EmptyState
          message={hasFilters ? 'No timeline events in this date range' : 'No timeline events recorded'}
          icon={<ClockIcon className="size-4 text-text-muted" />}
          className="rounded-xl border border-border-subtle p-8"
        />
      ) : (
        <div className="flex flex-col gap-5">
          {groups.map((group) => (
            <section key={group.key} className="flex flex-col gap-3">
              <h3 className="text-overline text-text-faint">{group.label}</h3>
              <ol className="flex flex-col">
                {group.events.map((event, index) => {
                  const { label, Icon, toneClass } = EVENT_STYLES[event.eventType] ?? GENERIC_STYLE
                  const isLast = index === group.events.length - 1
                  return (
                    <li key={`${event.occurredAt}-${event.eventType}-${index}`} className="relative flex gap-3 pb-4 last:pb-0">
                      {!isLast ? <span aria-hidden="true" className="absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 bg-border-subtle" /> : null}
                      <span className={`relative flex size-8 shrink-0 items-center justify-center rounded-full ${toneClass}`}>
                        <Icon className="size-4" />
                      </span>
                      <div className="flex min-w-0 flex-1 flex-col gap-1 rounded-xl border border-border-subtle bg-surface px-3 py-2">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="font-body text-[13px] font-semibold text-text">{label}</span>
                          <time dateTime={event.occurredAt} className="shrink-0 font-body text-[11px] text-text-muted">
                            {formatTime(event.occurredAt)}
                          </time>
                        </div>
                        <p className="font-body text-[13px] text-text-muted break-words">{event.summary}</p>
                        {event.actorName ? (
                          <span className="flex w-fit items-center gap-1 font-body text-[11px] font-medium text-text-faint">
                            <span className="size-1 rounded-full bg-text-faint" aria-hidden="true" />
                            by {event.actorName}
                          </span>
                        ) : null}
                      </div>
                    </li>
                  )
                })}
              </ol>
            </section>
          ))}
        </div>
      )}

      {isLoading && events.length > 0 ? <p className="font-body text-[12px] text-text-muted">Loading more…</p> : null}
      {error && events.length > 0 ? (
        <p role="alert" className="flex items-center gap-1.5 font-body text-[12px] text-danger">
          <AlertCircleIcon className="size-3.5" />
          {error}
          <button type="button" onClick={timeline.retry} className="font-semibold underline">
            Try again
          </button>
        </p>
      ) : null}
      {hasMore && !isLoading ? (
        <button
          type="button"
          onClick={() => void timeline.loadMore()}
          className="min-h-9 self-center rounded-lg border border-border-subtle px-4 font-body text-[12px] font-semibold text-secondary-accent hover:bg-surface-inset"
        >
          Load more
        </button>
      ) : null}
    </div>
  )
}
