import { Avatar } from '../ui/Avatar'
import { EmptyState } from '../ui/EmptyState'
import { formatTime } from '../../utils/format-time'
import type { DashboardRecentCheckin } from '../../../domain/entities/dashboard-checkin-schema'

interface RecentCheckinsCardProps {
  checkins: DashboardRecentCheckin[]
  employeeNameById: Record<string, string>
}

const COLUMN_HEADERS = ['NAME', 'HOST', 'TIME', 'STATUS']

export function RecentCheckinsCard({ checkins, employeeNameById }: RecentCheckinsCardProps) {
  return (
    <div className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-bold text-text">Recent Check-ins</h2>
        <button type="button" className="font-body text-sm font-semibold text-admin-accent">
          View All
        </button>
      </div>

      {checkins.length === 0 ? (
        <EmptyState message="No check-ins yet today." className="py-12" />
      ) : (
        <div className="w-full overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr>
                {COLUMN_HEADERS.map((header) => (
                  <th key={header} className="pb-2.5 font-body text-xs font-bold text-text-faint whitespace-nowrap">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {checkins.map((checkin) => {
                const isCheckedOut = checkin.checkedOutAt !== null
                const hostName = checkin.hostId ? (employeeNameById[checkin.hostId] ?? 'Unassigned') : 'Unassigned'

                return (
                  <tr key={checkin.id} className="border-t border-border-subtle">
                    <td className="py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={checkin.primaryContactFullName} size="sm" />
                        <span className="font-body text-sm font-semibold text-text">{checkin.primaryContactFullName}</span>
                      </div>
                    </td>
                    <td className="py-3 font-body text-sm text-text-muted whitespace-nowrap">{hostName}</td>
                    <td className="py-3 font-body text-sm text-text-muted whitespace-nowrap">{formatTime(checkin.checkedInAt)}</td>
                    <td className="py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                          isCheckedOut ? 'bg-border-subtle text-text-muted' : 'bg-success/15 text-success'
                        }`}
                      >
                        {isCheckedOut ? 'Checked Out' : 'Checked In'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
