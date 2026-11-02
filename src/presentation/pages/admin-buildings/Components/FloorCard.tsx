import { ChevronDownIcon, PencilIcon, TrashIcon } from '../../../components/icons'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { Department } from '../../../../domain/entities/department-schema'

interface FloorCardProps {
  floor: Floor
  departments: Department[]
  isExpanded: boolean
  onToggleExpand: () => void
  onEdit: () => void
  onDelete: () => void
}

export function FloorCard({ floor, departments, isExpanded, onToggleExpand, onEdit, onDelete }: FloorCardProps) {
  return (
    <div
      className={`flex w-full flex-col gap-3 rounded-2xl border p-4 ${
        isExpanded ? 'border-admin-accent/30 bg-admin-accent/5' : 'border-border bg-border-subtle'
      }`}
    >
      <div className="flex w-full items-center justify-between">
        <button type="button" onClick={onToggleExpand} aria-expanded={isExpanded} className="flex min-h-10 min-w-0 items-center gap-2.5 lg:min-h-0">
          <span className="font-body text-sm font-semibold text-text">{floor.name}</span>
          <ChevronDownIcon className={`size-3.5 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onEdit}
            aria-label={`Edit ${floor.name}`}
            className="flex size-10 items-center justify-center rounded-lg border border-border bg-surface lg:size-8"
          >
            <PencilIcon className="size-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Delete ${floor.name}`}
            className="flex size-10 items-center justify-center rounded-lg border border-border bg-surface lg:size-8"
          >
            <TrashIcon className="size-4" />
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="flex flex-col gap-3 pl-4">
          <div className="flex flex-wrap gap-4 font-body text-xs text-text-muted">
            <span>Floor {floor.floorNumber}</span>
            <span>
              Capacity: {floor.capacity} {floor.capacityType}
            </span>
            <span>Access: {floor.accessLevel}</span>
            <span>{floor.isActive ? 'Active' : 'Inactive'}</span>
          </div>

          <div className="flex flex-col gap-1">
            <p className="font-body text-sm font-semibold text-text-muted">Departments</p>
            <p className="font-body text-sm text-text-faint">
              {departments.length > 0 ? departments.map((department) => department.name).join(', ') : 'No departments assigned to this floor.'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
