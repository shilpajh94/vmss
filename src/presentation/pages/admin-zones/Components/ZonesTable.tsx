import { useNavigate } from 'react-router'
import type { Zone } from '../../../../domain/entities/zone-schema'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'
import { StatusBadge } from '../../../components/ui/StatusBadge'

// Below `md`: only the name, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4, 5, 6])

const COLUMN_HEADERS = ['ZONE NAME', 'CODE', 'BRANCH', 'BUILDING', 'FLOOR', 'GATES', 'STATUS']

interface ZoneNames {
  branch: Map<string, string>
  building: Map<string, string>
  floor: Map<string, string>
  gate: Map<string, string>
}

interface ZonesTableProps {
  zones: Zone[]
  names: ZoneNames
  canManage: boolean
  onDelete: (zone: Zone) => void
}

export function ZonesTable({ zones, names, canManage, onDelete }: ZonesTableProps) {
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
            {canManage && <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">ACTIONS</th>}
          </tr>
        </thead>
        <tbody>
          {zones.map((zone) => {
            const gateNames = zone.gateIds.map((id) => names.gate.get(id) ?? 'Unknown gate')
            return (
              <tr key={zone.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{zone.name}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{zone.code}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{names.branch.get(zone.branchId) ?? '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{(zone.buildingId && names.building.get(zone.buildingId)) || '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{(zone.floorId && names.floor.get(zone.floorId)) || '—'}</td>
                <td className="max-w-[220px] truncate px-6 py-4 font-body text-sm text-text-faint" title={gateNames.join(', ')}>
                  {gateNames.length > 0 ? gateNames.join(', ') : '—'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusBadge isActive={zone.isActive} />
                </td>
                {canManage && (
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => navigate(`/admin/zones/${zone.id}/edit`)}
                        aria-label={`Edit ${zone.name}`}
                        className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                      >
                        <PencilIcon className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(zone)}
                        aria-label={`Delete ${zone.name}`}
                        className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger"
                      >
                        <TrashIcon className="size-3.5" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
