import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4])

interface DepartmentsTableProps {
  departments: Department[]
  employees: HostEmployee[]
  onDelete: (department: Department) => void
}

const COLUMN_HEADERS = ['DEPARTMENT NAME', 'CODE', 'BRANCH', 'HEAD OF DEPARTMENT', 'STATUS']

export function DepartmentsTable({ departments, employees, onDelete }: DepartmentsTableProps) {
  const navigate = useNavigate()
  const employeesById = new Map(employees.map((employee) => [employee.id, employee]))

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
          {departments.map((department) => {
            const headOfDepartment = department.headOfDepartmentUserId
              ? employeesById.get(department.headOfDepartmentUserId)
              : undefined

            return (
              <tr key={department.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{department.name}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{department.code}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{department.branchName}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                  {headOfDepartment ? (
                    <div className="flex flex-col">
                      <span className="font-semibold text-text">{headOfDepartment.fullName}</span>
                      <span className="text-xs text-text-faint">{headOfDepartment.email}</span>
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                      department.isActive ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                    }`}
                  >
                    <span className={`size-1.5 rounded-full ${department.isActive ? 'bg-success' : 'bg-text-faint'}`} />
                    {department.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/departments/${department.id}/edit`)}
                      aria-label={`Edit ${department.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(department)}
                      aria-label={`Delete ${department.name}`}
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
