import { Link } from 'react-router'
import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { formatTime } from '../../utils/format-time'
import { CardHeader } from './CardHeader'
import { boardDrillDownPath, boardInvitationPath, type BoardBasePath } from './dashboard-format'
import type { DashboardRecentCheckin } from '../../../domain/entities/dashboard-checkin-schema'

interface RecentCheckinsCardProps {
  checkins: DashboardRecentCheckin[]
  boardBasePath: BoardBasePath
  branchId?: string
  className?: string
}

// Most recent check-ins first; each row opens the visit, and "View all"
// opens the board on both statuses the card lists.
export function RecentCheckinsCard({ checkins, boardBasePath, branchId, className = '' }: RecentCheckinsCardProps) {
  return (
    <section aria-label="Recent check-ins" className={`flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 ${className}`}>
      <CardHeader
        title="Recent Check-ins"
        subtitle="Latest arrivals and departures"
        viewAllHref={boardDrillDownPath(boardBasePath, { statuses: ['checked_in', 'checked_out'], branchId })}
        viewAllLabel="View all checked-in and checked-out visitors"
      />

      {checkins.length === 0 ? (
        <EmptyState message="No check-ins yet." className="py-12" />
      ) : (
        <ul className="flex flex-col">
          {checkins.map((checkin) => {
            const isInside = checkin.status === 'checked_in'

            return (
              <li key={checkin.id} className="border-t border-border-subtle first:border-t-0">
                <Link
                  to={boardInvitationPath(boardBasePath, checkin.id)}
                  className="flex min-h-14 items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-border-subtle focus-visible:outline-2 focus-visible:outline-admin-accent"
                >
                  <Avatar name={checkin.primaryContactFullName} size="sm" />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-body text-sm font-semibold text-text">{checkin.primaryContactFullName}</span>
                    <span className="truncate font-body text-xs text-text-faint">Host: {checkin.hostFullName ?? 'Unassigned'}</span>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="font-body text-xs text-text-muted tabular-nums">{formatTime(checkin.checkedInAt)}</span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 font-body text-[11px] font-semibold whitespace-nowrap ${
                        isInside ? 'bg-secondary-accent/10 text-secondary-accent' : 'bg-text-faint/15 text-text-muted'
                      }`}
                    >
                      {isInside ? 'Checked In' : 'Checked Out'}
                    </span>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
