import { PendingButton } from '../../components/ui/PendingButton'
import { TextField } from '../../components/ui/TextField'
import { useBadgeScan } from './hooks/use-badge-scan'

// Public (no staff login): a badge's signed QR text checks the visitor out or
// back in. Rendered inside PublicLayout.
export function BadgeScanPage() {
  const scan = useBadgeScan()
  const hasToken = scan.token.trim().length > 0

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-4 py-10">
      <h1 className="font-display text-xl font-bold text-text md:text-2xl">Badge scan</h1>
      <p className="font-body text-sm text-text-muted">Scan the visitor badge QR code, then choose what to do.</p>

      <form onSubmit={(event) => event.preventDefault()} className="flex flex-col gap-4">
        <TextField label="Badge code" value={scan.token} onChange={scan.setToken} autoComplete="off" disabled={scan.pending !== undefined} />
        <div className="flex gap-3">
          <PendingButton
            pending={scan.pending === 'check-in'}
            pendingLabel="Checking in…"
            disabled={!hasToken || scan.pending !== undefined}
            onClick={() => void scan.checkIn()}
            className="flex-1 rounded-full bg-primary px-4 py-2.5 font-body text-[13px] font-semibold text-on-primary disabled:opacity-50"
          >
            Check in
          </PendingButton>
          <PendingButton
            pending={scan.pending === 'check-out'}
            pendingLabel="Checking out…"
            disabled={!hasToken || scan.pending !== undefined}
            onClick={() => void scan.checkOut()}
            className="flex-1 rounded-full bg-primary px-4 py-2.5 font-body text-[13px] font-semibold text-on-primary disabled:opacity-50"
          >
            Check out
          </PendingButton>
          <PendingButton
            pending={scan.pending === 're-enter'}
            pendingLabel="Re-entering…"
            disabled={!hasToken || scan.pending !== undefined}
            onClick={() => void scan.reEnter()}
            className="flex-1 rounded-full border border-border bg-surface px-4 py-2.5 font-body text-[13px] font-semibold text-text disabled:opacity-50"
          >
            Re-enter
          </PendingButton>
        </div>
      </form>

      {scan.outcome?.kind === 'success' && (
        <p role="status" className="rounded-xl border border-border bg-surface p-4 font-body text-sm text-text">
          {scan.outcome.action === 'check-in' ? 'Checked in' : scan.outcome.action === 'check-out' ? 'Checked out' : 'Welcome back'}: {scan.outcome.result.trackingId}
          {scan.outcome.result.checkInStatus ? ` (${scan.outcome.result.checkInStatus})` : ''}
        </p>
      )}
      {scan.outcome?.kind === 'error' && (
        <p role="alert" className="font-body text-sm text-danger">
          {scan.outcome.message}
        </p>
      )}
      {scan.outcome?.kind === 'unavailable' && (
        <p role="status" className="font-body text-sm text-text-muted">
          Badge scanning is not available right now.
        </p>
      )}
    </main>
  )
}
