import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { FloorRow } from '../hooks/use-admin-floors'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4, 5])

interface FloorsTableProps {
  floors: FloorRow[]
  departmentNamesByFloorId: Map<string, string[]>
  onDelete: (floor: FloorRow) => void
}

const COLUMN_HEADERS = ['FLOOR NAME/NUMBER', 'BUILDING', 'DEPARTMENT(S)', 'CAPACITY', 'ACCESS LEVEL']

// Tinted badge + coloured dot, label in body text: readable in both themes
// (a status-coloured label on its own tint fails contrast for amber).
const ACCESS_LEVEL_STYLES: Record<FloorRow['accessLevel'], { label: string; bg: string; text: string; dot: string }> = {
  public: { label: 'Public', bg: 'bg-info/15', text: 'text-text', dot: 'bg-info' },
  restricted: { label: 'Restricted', bg: 'bg-warning/20', text: 'text-text', dot: 'bg-warning' },
  secure: { label: 'Secure', bg: 'bg-danger/15', text: 'text-text', dot: 'bg-danger' },
}

export function FloorsTable({ floors, departmentNamesByFloorId, onDelete }: FloorsTableProps) {
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
          {floors.map((floor) => {
            const accessLevel = ACCESS_LEVEL_STYLES[floor.accessLevel]
            const departmentNames = (departmentNamesByFloorId.get(floor.id) ?? []).join(', ')

            return (
              <tr key={floor.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">
                  {floor.name} <span className="text-text-faint">(#{floor.floorNumber})</span>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{floor.buildingName}</td>
                <td className="max-w-[175px] truncate px-6 py-4 font-body text-sm text-text-muted">{departmentNames || '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">
                  {floor.capacity} {floor.capacityType}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${accessLevel.bg} ${accessLevel.text}`}>
                    <span className={`size-1.5 rounded-full ${accessLevel.dot}`} />
                    {accessLevel.label}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                      floor.isActive ? 'bg-success/15 text-success-text' : 'bg-border-subtle text-text-muted'
                    }`}
                  >
                    <span className={`size-1.5 rounded-full ${floor.isActive ? 'bg-success' : 'bg-text-faint'}`} />
                    {floor.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/floors/${floor.id}/edit`)}
                      aria-label={`Edit ${floor.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(floor)}
                      aria-label={`Delete ${floor.name}`}
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
