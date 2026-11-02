import { useId } from 'react'
import type { CheckinSearchRow } from '../../../../domain/entities/checkin-schema'
import { PendingButton } from '../../../components/ui/PendingButton'

interface BadgeResultRowProps {
  row: CheckinSearchRow
  busy: boolean
  onVerifyId: () => void
  onUploadPhoto: (file: File) => void
  onPrint: () => void
  onReprint: () => void
}

function Indicator({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 font-body text-xs font-semibold ${ok ? 'bg-success/15 text-success' : 'bg-neutral-subtle text-text-muted'}`}>
      {label}
    </span>
  )
}

const BUTTON = 'rounded-full px-4 py-2 font-body text-[13px] font-semibold max-lg:min-h-10 disabled:opacity-50'

export function BadgeResultRow({ row, busy, onVerifyId, onUploadPhoto, onPrint, onReprint }: BadgeResultRowProps) {
  const photoInputId = useId()
  const idVerified = Boolean(row.idVerifiedAt)

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 md:flex-row md:items-center md:justify-between">
      <div className="flex min-w-0 flex-col gap-1.5">
        <p className="truncate font-body text-base font-semibold text-text">{row.fullName}</p>
        <p className="font-body text-[13px] text-text-muted">
          {row.trackingId}
          {row.phone ? ` · ${row.phone}` : ''}
        </p>
        <div className="flex flex-wrap gap-2">
          <Indicator ok label={row.checkInStatus ? `${row.status} · ${row.checkInStatus}` : row.status} />
          <Indicator ok={row.hasPhoto} label={row.hasPhoto ? 'Photo captured' : 'No photo'} />
          <Indicator ok={idVerified} label={idVerified ? 'ID verified' : 'ID not verified'} />
          <Indicator ok={row.hasActiveBadge} label={row.hasActiveBadge ? 'Badge active' : 'No badge'} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {!row.hasPhoto && (
          <>
            <input
              id={photoInputId}
              type="file"
              accept="image/jpeg,image/png"
              className="sr-only"
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (file) onUploadPhoto(file)
              }}
            />
            <label
              htmlFor={photoInputId}
              className={`${BUTTON} cursor-pointer border border-border bg-surface text-text ${busy ? 'pointer-events-none opacity-50' : ''}`}
            >
              Upload photo
            </label>
          </>
        )}
        {!idVerified && (
          <PendingButton pending={busy} onClick={onVerifyId} className={`${BUTTON} border border-border bg-surface text-text`}>
            ID verified
          </PendingButton>
        )}
        {row.hasActiveBadge ? (
          <button type="button" disabled={busy} onClick={onReprint} className={`${BUTTON} border border-border bg-surface text-text`}>
            Reprint…
          </button>
        ) : (
          <PendingButton pending={busy} pendingLabel="Printing…" onClick={onPrint} className={`${BUTTON} bg-primary text-on-primary`}>
            Print badge
          </PendingButton>
        )}
      </div>
    </li>
  )
}
