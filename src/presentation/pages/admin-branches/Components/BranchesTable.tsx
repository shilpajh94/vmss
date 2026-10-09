import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4])

interface BranchesTableProps {
  branches: Branch[]
  employees: HostEmployee[]
  onEdit: (branch: Branch) => void
  onDelete: (branch: Branch) => void
}

const COLUMN_HEADERS = ['BRANCH NAME', 'LOCATION / CITY', 'BRANCH CODE', 'CONTACT PERSON', 'STATUS']

export function BranchesTable({ branches, employees, onEdit, onDelete }: BranchesTableProps) {
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
          {branches.map((branch) => {
            const contactPerson = employeesById.get(branch.contactPersonUserId)

            return (
              <tr key={branch.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{branch.name}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{branch.city}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{branch.code}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                  {contactPerson ? (
                    <div className="flex flex-col">
                      <span className="font-semibold text-text">{contactPerson.fullName}</span>
                      <span className="text-xs text-text-faint">{contactPerson.email}</span>
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                      branch.isActive ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                    }`}
                  >
                    <span className={`size-1.5 rounded-full ${branch.isActive ? 'bg-success' : 'bg-text-faint'}`} />
                    {branch.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => onEdit(branch)}
                      aria-label={`Edit ${branch.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(branch)}
                      aria-label={`Delete ${branch.name}`}
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
