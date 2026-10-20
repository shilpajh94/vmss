import { AsyncRegion } from '../../components/AsyncRegion'
import { EmptyState } from '../../components/ui/EmptyState'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { ActivityTable } from './Components/ActivityTable'
import { AuditFilterBar } from './Components/AuditFilterBar'
import { useAdminAuditTrail } from './hooks/use-admin-audit-trail'
import { PAGE_SIZE } from './types'

export function AdminAuditTrailPage() {
  const {
    dateRange,
    activityType,
    page,
    entries,
    total,
    employeeNameById,
    phase,
    isRefreshing,
    changeDateRange,
    changeActivityType,
    goToNextPage,
    goToPrevPage,
    retry,
    downloadingFormat,
    downloadReport,
  } = useAdminAuditTrail()

  usePageHeader({ description: 'Organisation-wide activity log of account and invitation actions' })

  // Pinned below the scrolling rows, not inside them, so it never scrolls
  // out of view (responsive-layout "Paged List Pagination Stays Visible
  // Below the Data").
  const pagination =
    phase === 'ready' && entries.length > 0 ? (
      <div className="flex-none">
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
      </div>
    ) : undefined

  return (
    <PageContentLayout
      fitBody={entries.length > 0}
      footer={pagination}
      header={
        <>
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">Audit Trail</h1>
          <AuditFilterBar
            dateRange={dateRange}
            onDateRangeChange={changeDateRange}
            activityType={activityType}
            onActivityTypeChange={changeActivityType}
            downloadingFormat={downloadingFormat}
            onDownload={(format) => void downloadReport(format)}
          />
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={4} rows={PAGE_SIZE} label="Loading audit trail…" />}
        errorMessage="Something went wrong loading the audit trail. Please try again."
        onRetry={retry}
        isEmpty={entries.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-xl border border-border bg-surface py-16">
            <EmptyState message="No activity matches the current filters." />
          </div>
        }
      >
        {/* min-w-0: the table scrolls inside its own box rather than widening the page. */}
        <div className="w-full min-w-0">
          <ActivityTable entries={entries} employeeNameById={employeeNameById} />
        </div>
      </AsyncRegion>
    </PageContentLayout>
  )
}
