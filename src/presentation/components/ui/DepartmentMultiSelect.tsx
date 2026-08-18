import { Checkbox } from './Checkbox'
import type { Department } from '../../../domain/entities/department-schema'

interface DepartmentMultiSelectProps {
  departments: Department[]
  selectedIds: string[]
  onChange: (selectedIds: string[]) => void
}

export function DepartmentMultiSelect({ departments, selectedIds, onChange }: DepartmentMultiSelectProps) {
  const toggle = (departmentId: string, checked: boolean) => {
    if (checked) {
      onChange([...selectedIds, departmentId])
    } else {
      onChange(selectedIds.filter((id) => id !== departmentId))
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-body font-medium text-text">Department(s)</p>
      <div className="flex max-h-40 flex-col gap-2 overflow-y-auto rounded-lg border border-border p-3">
        {departments.length === 0 ? (
          <p className="text-caption text-text-muted">No departments available.</p>
        ) : (
          departments.map((department) => (
            <Checkbox
              key={department.id}
              checked={selectedIds.includes(department.id)}
              onChange={(checked) => toggle(department.id, checked)}
            >
              {department.name}
            </Checkbox>
          ))
        )}
      </div>
    </div>
  )
}
