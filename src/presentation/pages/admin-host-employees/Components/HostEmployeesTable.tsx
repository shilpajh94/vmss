import { useNavigate } from 'react-router'
import { PencilIcon } from '../../../components/icons'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

interface HostEmployeesTableProps {
  hostEmployees: HostEmployee[]
  departmentNameById: Map<string, string>
}

const COLUMN_HEADERS = ['EMPLOYEE NAME', 'DEPARTMENT', 'EMAIL ADDRESS', 'ROLES', 'STATUS']

export function HostEmployeesTable({ hostEmployees, departmentNameById }: HostEmployeesTableProps) {
  const navigate = useNavigate()

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className="w-full text-left">
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
                  <span className="size-9 shrink-0 rounded-full bg-neutral-subtle" />
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
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                    hostEmployee.isActive ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                  }`}
                >
                  <span className={`size-1.5 rounded-full ${hostEmployee.isActive ? 'bg-success' : 'bg-text-faint'}`} />
                  {hostEmployee.isActive ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/host-employees/${hostEmployee.id}/edit`)}
                    aria-label={`Manage access for ${hostEmployee.fullName}`}
                    className="flex items-center justify-center rounded-lg bg-border-subtle p-2 text-text"
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
