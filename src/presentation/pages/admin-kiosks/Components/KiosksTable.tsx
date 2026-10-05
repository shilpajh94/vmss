import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { Kiosk } from '../../../../domain/entities/kiosk-schema'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([2])

interface KiosksTableProps {
  kiosks: Kiosk[]
  canManage: boolean
  busyKioskId: string | undefined
  onToggleActive: (kiosk: Kiosk) => void
  onToggleHidden: (kiosk: Kiosk) => void
  onDelete: (kiosk: Kiosk) => void
}

export function KiosksTable({ kiosks, canManage, busyKioskId, onToggleActive, onToggleHidden, onDelete }: KiosksTableProps) {
  const navigate = useNavigate()
  const headerClassName = 'px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap'

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className={TABLE_CLASS_NAME}>
        <thead>
          <tr className="bg-border-subtle">
            <th className={headerClassName}>NAME</th>
            <th className={headerClassName}>DESCRIPTION</th>
            <th className={headerClassName}>STATUS</th>
            {canManage && <th className={`${headerClassName} text-right`}>ACTIONS</th>}
          </tr>
        </thead>
        <tbody>
          {kiosks.map((kiosk) => {
            const isBusy = busyKioskId === kiosk.id

            return (
              <tr key={kiosk.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    {kiosk.name}
                    {kiosk.isHidden && (
                      <span className="inline-flex items-center rounded bg-neutral-subtle px-2.5 py-1 font-body text-[11px] font-bold text-text-muted">
                        Hidden
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted">{kiosk.description || '—'}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {canManage ? (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={kiosk.isActive}
                      aria-label={`${kiosk.isActive ? 'Deactivate' : 'Activate'} ${kiosk.name}`}
                      disabled={isBusy}
                      onClick={() => onToggleActive(kiosk)}
                      className="flex items-center gap-2 disabled:opacity-50"
                    >
                      <span className={`relative h-5 w-9 rounded-full transition-colors ${kiosk.isActive ? 'bg-admin-accent' : 'bg-neutral-subtle'}`}>
                        <span
                          className={`absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition-transform ${kiosk.isActive ? 'translate-x-4' : ''}`}
                        />
                      </span>
                      <span className="font-body text-[13px] font-semibold text-text-muted">{kiosk.isActive ? 'Active' : 'Inactive'}</span>
                    </button>
                  ) : (
                    <span
                      className={`inline-flex items-center rounded px-2.5 py-1 font-body text-[11px] font-bold ${
                        kiosk.isActive ? 'bg-success/15 text-success' : 'bg-neutral-subtle text-text-muted'
                      }`}
                    >
                      {kiosk.isActive ? 'Active' : 'Inactive'}
                    </span>
                  )}
                </td>
                {canManage && (
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onToggleHidden(kiosk)}
                        disabled={isBusy}
                        className="rounded-lg bg-border-subtle px-3 py-2 font-body text-[12px] font-semibold text-text disabled:opacity-50"
                      >
                        {kiosk.isHidden ? 'Unhide' : 'Hide'}
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate(`/admin/kiosks/${kiosk.id}/edit`)}
                        aria-label={`Edit ${kiosk.name}`}
                        className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                      >
                        <PencilIcon className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(kiosk)}
                        aria-label={`Delete ${kiosk.name}`}
                        className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger"
                      >
                        <TrashIcon className="size-3.5" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
