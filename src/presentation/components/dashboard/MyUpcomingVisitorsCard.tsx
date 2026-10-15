import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { formatDate, formatTime } from '../../utils/format-time'
import type { MyUpcomingVisitor } from '../../../domain/entities/my-dashboard-overview-schema'

interface MyUpcomingVisitorsCardProps {
  visitors: MyUpcomingVisitor[]
  onOpen: (invitationId: string) => void
}

// The visit date/time arrive as plain local values ("2026-10-22", "14:00:00");
// joined without a zone so they parse as local time, never shifted by UTC.
function scheduledLocal(visitor: MyUpcomingVisitor): string | null {
  if (!visitor.preferredVisitDate) return null
  return `${visitor.preferredVisitDate}T${visitor.preferredVisitTime ?? '00:00:00'}`
}

export function MyUpcomingVisitorsCard({ visitors, onOpen }: MyUpcomingVisitorsCardProps) {
  return (
    <div className="flex w-full flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <div className="flex flex-col gap-0.5">
        <h2 className="font-display text-lg font-bold text-text">Your Upcoming Visitors</h2>
        <p className="font-body text-sm text-text-faint">Approved visits you're involved in, soonest first</p>
      </div>

      {visitors.length === 0 ? (
        <EmptyState message="No upcoming visitors scheduled." className="py-12" />
      ) : (
        <div className="flex flex-col">
          {visitors.map((visitor) => {
            const scheduled = scheduledLocal(visitor)

            return (
              <button
                key={visitor.id}
                type="button"
                onClick={() => onOpen(visitor.id)}
                className="flex flex-wrap items-center gap-4 border-t border-border-subtle py-4 text-left first:border-t-0 hover:bg-border-subtle"
              >
                <div className="flex w-24 shrink-0 flex-col font-body text-sm">
                  <span className="font-semibold text-text">{formatDate(scheduled)}</span>
                  {visitor.preferredVisitTime ? <span className="text-text-muted">{formatTime(scheduled)}</span> : null}
                </div>

                <div className="flex flex-1 basis-56 items-center gap-3">
                  <Avatar name={visitor.primaryContactFullName} size="sm" />
                  <div className="flex flex-col">
                    <span className="font-body text-sm font-semibold text-text">{visitor.primaryContactFullName}</span>
                    <span className="font-body text-xs text-text-faint">{visitor.trackingId}</span>
                  </div>
                </div>

                <div className="ml-auto flex basis-52 items-center gap-2 font-body text-sm text-text-muted">
                  <span className="size-1.5 rounded-full bg-admin-accent" />
                  {visitor.purposeOfVisit ?? 'Not specified'}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
