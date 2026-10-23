import { useNavigate } from 'react-router'
import { PencilIcon } from '../../../components/icons'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'
import { Avatar } from '../../../components/ui/Avatar'
import { StatusBadge } from '../../../components/ui/StatusBadge'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4])

interface HostEmployeesTableProps {
  hostEmployees: HostEmployee[]
  departmentNameById: Map<string, string>
}

const COLUMN_HEADERS = ['EMPLOYEE NAME', 'DEPARTMENT', 'EMAIL ADDRESS', 'ROLES', 'STATUS']

export function HostEmployeesTable({ hostEmployees, departmentNameById }: HostEmployeesTableProps) {
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
          {hostEmployees.map((hostEmployee) => (
            <tr key={hostEmployee.id} className="border-b border-border-subtle">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center gap-3">
                  <Avatar name={hostEmployee.fullName} photoUrl={hostEmployee.avatarUrl} size="lg" />
                  <span className="font-body text-sm font-semibold text-text">{hostEmployee.fullName}</span>
                </div>
              </td>
              <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                {hostEmployee.departmentId ? departmentNameById.get(hostEmployee.departmentId) ?? '—' : '—'}
              </td>
              <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{hostEmployee.email}</td>
              <td className="px-6 py-4 whitespace-nowrap">
                {hostEmployee.branchRoles.length === 0 ? (
                  <span className="font-body text-xs text-text-faint">No roles assigned</span>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {hostEmployee.branchRoles.map((role) => (
                      <span
                        key={role.id}
                        className="inline-flex items-center rounded-full bg-admin-accent/15 px-2.5 py-1 font-body text-xs font-semibold text-admin-accent"
                      >
                        {role.roleName}
                      </span>
                    ))}
                  </div>
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <StatusBadge isActive={hostEmployee.isActive} />
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/host-employees/${hostEmployee.id}/edit`)}
                    aria-label={`Manage access for ${hostEmployee.fullName}`}
                    className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                  >
                    <PencilIcon className="size-3.5" />
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
