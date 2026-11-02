import { Link } from 'react-router'
import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { formatDate, formatTime } from '../../utils/format-time'
import { CardHeader } from './CardHeader'
import { boardDrillDownPath, boardInvitationPath, scheduledLocal, type BoardBasePath } from './dashboard-format'
import { purposeLabel } from '../../utils/purpose-of-visit-options'

export interface UpcomingVisitorRow {
  id: string
  trackingId: string
  primaryContactFullName: string
  // Omitted on the personal dashboard, where the reader is (one of) the hosts.
  hostFullName?: string | null
  purposeOfVisit: string | null
  preferredVisitDate: string | null
  preferredVisitTime: string | null
  expiresAt: string
}

interface UpcomingVisitorsCardProps {
  title: string
  subtitle: string
  visitors: UpcomingVisitorRow[]
  boardBasePath: BoardBasePath
  branchId?: string
  showHost: boolean
  className?: string
}

// Approved visitors not yet admitted. Each row shows the scheduled visit
// (falling back to the pass's expiry when no visit date is set) and opens the
// visit; "View all" opens the board on the same upcoming invitations the
// Upcoming tile counts.
export function UpcomingVisitorsCard({ title, subtitle, visitors, boardBasePath, branchId, showHost, className = '' }: UpcomingVisitorsCardProps) {
  return (
    <section aria-label={title} className={`flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 ${className}`}>
      <CardHeader title={title} subtitle={subtitle} viewAllHref={boardDrillDownPath(boardBasePath, { upcoming: true, branchId })}
        viewAllLabel="View all upcoming visitors"
      />

      {visitors.length === 0 ? (
        <EmptyState message="No upcoming visitors scheduled." className="py-12" />
      ) : (
        <ul className="flex flex-col">
          {visitors.map((visitor) => {
            const scheduled = scheduledLocal(visitor.preferredVisitDate, visitor.preferredVisitTime)

            return (
              <li key={visitor.id} className="border-t border-border-subtle first:border-t-0">
                <Link
                  to={boardInvitationPath(boardBasePath, visitor.id)}
                  className="flex min-h-14 items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-border-subtle focus-visible:outline-2 focus-visible:outline-admin-accent"
                >
                  <div className="flex w-16 shrink-0 flex-col font-body text-sm">
                    <span className="font-semibold text-text">{formatDate(scheduled ?? visitor.expiresAt)}</span>
                    <span className="text-xs text-text-muted">{visitor.preferredVisitTime ? formatTime(scheduled) : scheduled ? 'Any time' : 'Valid until'}</span>
                  </div>
                  <Avatar name={visitor.primaryContactFullName} size="sm" />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-body text-sm font-semibold text-text">{visitor.primaryContactFullName}</span>
                    <span className="truncate font-body text-xs text-text-faint">
                      {showHost ? `Host: ${visitor.hostFullName ?? 'Unassigned'} · ` : ''}
                      {purposeLabel(visitor.purposeOfVisit) ?? 'Not specified'}
                    </span>
                  </div>
                  <span className="hidden shrink-0 font-body text-xs text-text-faint sm:inline">{visitor.trackingId}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
