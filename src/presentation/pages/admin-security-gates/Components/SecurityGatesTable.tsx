import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { SecurityGate } from '../../../../domain/entities/security-gate-schema'

interface SecurityGatesTableProps {
  securityGates: SecurityGate[]
  onDelete: (securityGate: SecurityGate) => void
}

const COLUMN_HEADERS = ['GATE NAME/ID', 'CODE', 'BUILDING', 'GATE TYPE', 'AUTH METHOD']

const GATE_TYPE_BADGE: Record<SecurityGate['gateType'], { label: string; className: string }> = {
  both: { label: 'Entry & Exit', className: 'bg-info/15 text-info' },
  entry: { label: 'Entry Only', className: 'bg-success/15 text-success' },
  exit: { label: 'Exit Only', className: 'bg-danger/15 text-danger' },
}

const CONNECTIVITY_BADGE: Record<SecurityGate['connectivityStatus'], { label: string; badgeClassName: string; dotClassName: string }> = {
  online: { label: 'Online', badgeClassName: 'bg-success/15 text-success', dotClassName: 'bg-success' },
  maintenance: { label: 'Maintenance', badgeClassName: 'bg-warning/15 text-warning', dotClassName: 'bg-warning' },
  offline: { label: 'Offline', badgeClassName: 'bg-border-subtle text-text-muted', dotClassName: 'bg-text-faint' },
}

export function SecurityGatesTable({ securityGates, onDelete }: SecurityGatesTableProps) {
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
            <th className="px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap">CONNECTIVITY</th>
            <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {securityGates.map((securityGate) => {
            const gateTypeBadge = GATE_TYPE_BADGE[securityGate.gateType]
            const connectivityBadge = CONNECTIVITY_BADGE[securityGate.connectivityStatus]

            return (
              <tr key={securityGate.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{securityGate.name}</td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{securityGate.code}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{securityGate.buildingName}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span className={`inline-flex items-center rounded px-2.5 py-1 font-body text-[11px] font-bold ${gateTypeBadge.className}`}>
                      {gateTypeBadge.label}
                    </span>
                    {securityGate.highSecurity && (
                      <span className="inline-flex items-center rounded px-2.5 py-1 font-body text-[11px] font-bold bg-warning/15 text-warning">
                        High Security
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{securityGate.authMethod ?? '—'}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${connectivityBadge.badgeClassName}`}
                  >
                    <span className={`size-1.5 rounded-full ${connectivityBadge.dotClassName}`} />
                    {connectivityBadge.label}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/security-gates/${securityGate.id}/edit`)}
                      aria-label={`Edit ${securityGate.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(securityGate)}
                      aria-label={`Delete ${securityGate.name}`}
                      className="flex items-center justify-center rounded-lg bg-danger/15 p-2 text-danger"
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
