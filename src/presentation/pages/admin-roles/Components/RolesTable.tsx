import { useNavigate } from 'react-router'
import { PencilIcon } from '../../../components/icons'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3])

interface RolesTableProps {
  roles: RoleOut[]
}

const COLUMN_HEADERS = ['ROLE NAME', 'DESCRIPTION', 'PERMISSIONS', 'TYPE']

export function RolesTable({ roles }: RolesTableProps) {
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
          {roles.map((role) => (
            <tr key={role.id} className="border-b border-border-subtle">
              <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{role.name}</td>
              <td className="px-6 py-4 font-body text-sm text-text-muted">{role.description ?? '—'}</td>
              <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                {role.permissionCodes.length} permission{role.permissionCodes.length === 1 ? '' : 's'}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                    role.isStandard ? 'bg-info/15 text-info' : 'bg-border-subtle text-text-muted'
                  }`}
                >
                  {role.isStandard ? 'Standard' : 'Custom'}
                </span>
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/roles/${role.id}/edit`)}
                    aria-label={`Edit permissions for ${role.name}`}
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
