import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { formatDate } from '../../utils/format-time'
import type { DashboardUpcomingVisitor } from '../../../domain/entities/dashboard-overview-schema'

interface UpcomingVisitorsCardProps {
  visitors: DashboardUpcomingVisitor[]
  employeeNameById: Record<string, string>
}

export function UpcomingVisitorsCard({ visitors, employeeNameById }: UpcomingVisitorsCardProps) {
  return (
    <div className="flex w-full flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <div className="flex flex-col gap-0.5">
        <h2 className="font-display text-lg font-bold text-text">Upcoming Pre-Registered Visitors</h2>
        <p className="font-body text-sm text-text-faint">Pre-registered visitors awaiting check-in</p>
      </div>

      {visitors.length === 0 ? (
        <EmptyState message="No upcoming visitors scheduled." className="py-12" />
      ) : (
        <div className="flex flex-col">
          {visitors.map((visitor) => {
            const hostName = visitor.hostId ? (employeeNameById[visitor.hostId] ?? 'Unassigned') : 'Unassigned'

            return (
              <div key={visitor.id} className="flex flex-wrap items-center gap-4 border-t border-border-subtle py-4 first:border-t-0">
                <div className="w-24 shrink-0 font-body text-sm font-semibold text-text">{formatDate(visitor.expiresAt)}</div>

                <div className="flex flex-1 items-center gap-3 basis-56">
                  <Avatar name={visitor.primaryContactFullName} size="sm" />
                  <span className="font-body text-sm font-semibold text-text">{visitor.primaryContactFullName}</span>
                </div>

                <div className="flex basis-44 items-center gap-1 font-body text-sm text-text-muted">
                  <span>Host:</span>
                  <span className="font-semibold text-text">{hostName}</span>
                </div>

                <div className="ml-auto flex basis-52 items-center gap-2 font-body text-sm text-text-muted">
                  <span className="size-1.5 rounded-full bg-admin-accent" />
                  {visitor.purposeOfVisit ?? 'Not specified'}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
