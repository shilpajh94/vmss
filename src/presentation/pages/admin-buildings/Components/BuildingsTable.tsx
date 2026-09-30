import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { Building } from '../../../../domain/entities/building-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4])

interface BuildingsTableProps {
  buildings: Building[]
  onDelete: (building: Building) => void
}

const COLUMN_HEADERS = ['BUILDING NAME', 'BRANCH', 'CODE', 'ADDRESS', 'STATUS']

export function BuildingsTable({ buildings, onDelete }: BuildingsTableProps) {
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
            <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {buildings.map((building) => (
            <tr key={building.id} className="border-b border-border-subtle">
              <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{building.name}</td>
              <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{building.branchName}</td>
              <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{building.code}</td>
              <td className="max-w-[175px] truncate px-6 py-4 font-body text-sm text-text-faint">{building.address || '—'}</td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                    building.isActive ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                  }`}
                >
                  <span className={`size-1.5 rounded-full ${building.isActive ? 'bg-success' : 'bg-text-faint'}`} />
                  {building.isActive ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/buildings/${building.id}/edit`)}
                    aria-label={`Edit ${building.name}`}
                    className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                  >
                    <PencilIcon className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(building)}
                    aria-label={`Delete ${building.name}`}
                    className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger"
                  >
                    <TrashIcon className="size-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
