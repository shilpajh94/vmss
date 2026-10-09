import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { ReceptionDesk } from '../../../../domain/entities/reception-desk-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4, 5, 6])

interface ReceptionDesksTableProps {
  receptionDesks: ReceptionDesk[]
  onDelete: (receptionDesk: ReceptionDesk) => void
}

const COLUMN_HEADERS = ['DESK NAME', 'CODE', 'BUILDING', 'FLOOR', 'ASSIGNED RECEPTIONIST', 'OPERATING HOURS']

const STATUS_BADGE: Record<ReceptionDesk['status'], { label: string; badgeClassName: string; dotClassName: string }> = {
  active: { label: 'Active', badgeClassName: 'bg-success/15 text-success', dotClassName: 'bg-success' },
  maintenance: { label: 'Maintenance', badgeClassName: 'bg-warning/15 text-warning', dotClassName: 'bg-warning' },
  inactive: { label: 'Inactive', badgeClassName: 'bg-border-subtle text-text-muted', dotClassName: 'bg-text-faint' },
}

function formatOperatingHours(receptionDesk: ReceptionDesk): string {
  if (!receptionDesk.operatingHoursFrom && !receptionDesk.operatingHoursTo) return '—'
  return `${receptionDesk.operatingHoursFrom ?? '—'} - ${receptionDesk.operatingHoursTo ?? '—'}`
}

export function ReceptionDesksTable({ receptionDesks, onDelete }: ReceptionDesksTableProps) {
  const navigate = useNavigate()

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className={TABLE_CLASS_NAME}>
        <thead>
          <tr className="bg-border-subtle">
            {COLUMN_HEADERS.map((header) => (
              <th key={header} className="px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap">
                {header}
              </th>
            ))}
            <th className="px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap">STATUS</th>
            <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {receptionDesks.map((receptionDesk) => {
            const statusBadge = STATUS_BADGE[receptionDesk.status]

            return (
              <tr key={receptionDesk.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{receptionDesk.name}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{receptionDesk.code}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{receptionDesk.buildingName}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{receptionDesk.floorName ?? '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{receptionDesk.receptionistName ?? 'Unassigned'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{formatOperatingHours(receptionDesk)}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${statusBadge.badgeClassName}`}
                  >
                    <span className={`size-1.5 rounded-full ${statusBadge.dotClassName}`} />
                    {statusBadge.label}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/reception-desks/${receptionDesk.id}/edit`)}
                      aria-label={`Edit ${receptionDesk.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(receptionDesk)}
                      aria-label={`Delete ${receptionDesk.name}`}
                      className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger"
                    >
                      <TrashIcon className="size-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
