import { TrashIcon } from '../../../components/icons'
import type { Device } from '../../../../domain/entities/managed-device-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'
import { formatDateTime } from '../../../utils/format-time'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2, 3, 4, 6])

interface DevicesTableProps {
  devices: Device[]
  canManage: boolean
  busyDeviceId: string | undefined
  onApprove: (device: Device) => void
  onEnable: (device: Device) => void
  onDisable: (device: Device) => void
  onDelete: (device: Device) => void
}

function statusBadge(device: Device): { label: string; className: string } {
  if (device.approvalStatus === 'pending') return { label: 'Pending Approval', className: 'bg-warning/15 text-warning' }
  if (device.isActive) return { label: 'Approved', className: 'bg-success/15 text-success-text' }
  return { label: 'Disabled', className: 'bg-neutral-subtle text-text-muted' }
}

export function DevicesTable({ devices, canManage, busyDeviceId, onApprove, onEnable, onDisable, onDelete }: DevicesTableProps) {
  const headerClassName = 'px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap'
  const actionClassName = 'rounded-lg bg-border-subtle px-3 py-2 font-body text-[12px] font-semibold text-text disabled:opacity-50'

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className={TABLE_CLASS_NAME}>
        <thead>
          <tr className="bg-border-subtle">
            <th className={headerClassName}>NAME / DEVICE ID</th>
            <th className={headerClassName}>BRANCH</th>
            <th className={headerClassName}>BUILDING</th>
            <th className={headerClassName}>REGISTERED</th>
            <th className={headerClassName}>STATUS</th>
            <th className={headerClassName}>APPROVED</th>
            <th className={`${headerClassName} text-right`}>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => {
            const isBusy = busyDeviceId === device.id
            const badge = statusBadge(device)

            return (
              <tr key={device.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 whitespace-nowrap">
                  <p className="font-body text-sm font-semibold text-text">{device.name}</p>
                  <p className="font-body text-[12px] text-text-muted">{device.deviceId}</p>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{device.branchName || '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{device.buildingName || '—'}</td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{formatDateTime(device.createdAt)}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`inline-flex items-center rounded px-2.5 py-1 font-body text-[11px] font-bold ${badge.className}`}>
                    {badge.label}
                  </span>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                  {device.approvedAt ? formatDateTime(device.approvedAt) : '—'}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    {device.canApprove && (
                      <button type="button" onClick={() => onApprove(device)} disabled={isBusy} className={`${actionClassName} !bg-admin-accent !text-on-accent`}>
                        Approve
                      </button>
                    )}
                    {device.approvalStatus === 'approved' && device.canEnable && (
                      <button type="button" onClick={() => onEnable(device)} disabled={isBusy} className={actionClassName}>
                        Enable
                      </button>
                    )}
                    {device.approvalStatus === 'approved' && device.canDisable && (
                      <button type="button" onClick={() => onDisable(device)} disabled={isBusy} className={actionClassName}>
                        Disable
                      </button>
                    )}
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => onDelete(device)}
                        disabled={isBusy}
                        aria-label={`Delete ${device.name}`}
                        className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger disabled:opacity-50"
                      >
                        <TrashIcon className="size-3.5" />
                      </button>
                    )}
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
