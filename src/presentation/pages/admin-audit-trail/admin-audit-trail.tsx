import { LoadingState } from '../../components/ui/LoadingState'
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
    isLoading,
    errorMessage,
    changeDateRange,
    changeActivityType,
    goToNextPage,
    goToPrevPage,
    retry,
    downloadingFormat,
    downloadReport,
  } = useAdminAuditTrail()

  usePageHeader({ description: 'Organisation-wide activity log of account and invitation actions' })

  return (
    <PageContentLayout
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
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading audit trail…" className="flex-1" />
      ) : (
        <div className="flex flex-col gap-6">
          <ActivityTable entries={entries} employeeNameById={employeeNameById} />
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      )}
    </PageContentLayout>
  )
}
