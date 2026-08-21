import { EmptyState } from '../../../components/ui/EmptyState'
import type { DashboardRecentCheckin } from '../../../../domain/entities/dashboard-overview-schema'

interface RecentCheckinsCardProps {
  checkins: DashboardRecentCheckin[]
}

const COLUMN_HEADERS = ['NAME', 'HOST', 'TIME', 'BADGE #', 'STATUS']

export function RecentCheckinsCard({ checkins }: RecentCheckinsCardProps) {
  return (
    <div className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
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
              {checkins.map((checkin) => (
                <tr key={checkin.id} className="border-t border-border-subtle">
                  <td className="py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2.5">
                      <span className="size-7 shrink-0 rounded-full bg-neutral-subtle" />
                      <span className="font-body text-sm font-semibold text-text">{checkin.visitorName}</span>
                    </div>
                  </td>
                  <td className="py-3 font-body text-sm text-text-muted whitespace-nowrap">{checkin.hostName}</td>
                  <td className="py-3 font-body text-sm text-text-muted whitespace-nowrap">{checkin.time}</td>
                  <td className="py-3 font-body text-sm text-admin-accent whitespace-nowrap">{checkin.badgeNumber}</td>
                  <td className="py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                        checkin.status === 'checked-in' ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                      }`}
                    >
                      {checkin.status === 'checked-in' ? 'Checked In' : 'Checked Out'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
