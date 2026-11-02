import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { usePageHeader } from '../../context/page-header-context'
import { useBadgePrintFlow } from '../../hooks/use-badge-print-flow'
import { LoadingState } from '../../components/ui/LoadingState'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { TextField } from '../../components/ui/TextField'
import { Pagination } from '../../components/Pagination'
import { useBadgePrinting } from './hooks/use-badge-printing'
import { BadgeResultRow } from './Components/BadgeResultRow'
import { ReprintDialog } from './Components/ReprintDialog'

// Rendered inside StaffLayout. Gated by the tenant toggle plus
// `visitors:print_badge` (the route's `requires` covers the permission).
export function ReceptionBadgePrintingPage() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const flow = useBadgePrintFlow()
  const printing = useBadgePrinting()

  usePageHeader({ description: 'Find a visit, check the ID, and print the visitor badge' })

  useEffect(() => {
    // Shared by the Reception (staff layout) and Admin routes: leave for the matching dashboard.
    if (flow === 'off') navigate(pathname.startsWith('/admin') ? '/admin/dashboard' : '/reception/dashboard', { replace: true })
  }, [flow, navigate, pathname])

  if (flow !== 'on') return <LoadingState label="Loading…" />

  if (printing.isUnavailable) {
    return (
      <>
        <h1 className="font-display text-xl font-bold md:text-2xl text-text">Badge printing</h1>
        <EmptyState message="Badge printing is not available right now." />
      </>
    )
  }

  return (
    <>
      <h1 className="font-display text-xl font-bold md:text-2xl text-text">Badge printing</h1>

      <form onSubmit={printing.submitSearch} className="flex w-full max-w-xl items-end gap-3">
        <div className="flex-1">
          <TextField
            label="Find a visit"
            value={printing.draft}
            onChange={printing.setDraft}
            placeholder="Name, phone, invitation code or SMS check-in code"
          />
        </div>
        <button
          type="submit"
          disabled={!printing.draft.trim() || printing.isLoading}
          className="rounded-full bg-primary px-[18px] py-2.5 font-body text-[13px] font-semibold text-on-primary disabled:opacity-50"
        >
          Search
        </button>
      </form>

      {printing.pdfLink && (
        <p role="status" className="font-body text-sm text-text">
          Your browser blocked the badge window.{' '}
          <a href={printing.pdfLink} target="_blank" rel="noreferrer" className="font-semibold text-admin-accent underline">
            Open badge PDF
          </a>
        </p>
      )}

      {printing.loadError ? (
        <ErrorState message={printing.loadError} onRetry={() => void printing.retry()} />
      ) : printing.isLoading && printing.rows.length === 0 ? (
        <LoadingState label="Searching…" />
      ) : !printing.hasSearched ? null : printing.rows.length === 0 ? (
        <EmptyState message="No visits match your search." />
      ) : (
        <>
          <ul className="flex w-full flex-col gap-3">
            {printing.rows.map((row) => (
              <BadgeResultRow
                key={row.id}
                row={row}
                busy={printing.busyId === row.id}
                onVerifyId={() => void printing.verifyId(row)}
                onUploadPhoto={(file) => void printing.uploadPhoto(row, file)}
                onPrint={() => void printing.printBadge(row)}
                onReprint={() => printing.startReprint(row)}
              />
            ))}
          </ul>
          <Pagination
            page={printing.page}
            pageSize={printing.pageSize}
            total={printing.total}
            onPrev={printing.prevPage}
            onNext={printing.nextPage}
            itemLabel="visits"
          />
        </>
      )}

      <ReprintDialog
        target={printing.reprintTarget}
        reason={printing.reason}
        reasonValid={printing.reasonValid}
        busy={printing.busyId !== undefined}
        onReasonChange={printing.setReason}
        onCancel={printing.cancelReprint}
        onConfirm={() => void printing.confirmReprint()}
      />
    </>
  )
}
