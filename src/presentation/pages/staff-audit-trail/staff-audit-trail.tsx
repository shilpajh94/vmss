import { LoadingState } from '../../components/ui/LoadingState'
import { ActivityTable } from './Components/ActivityTable'
import { AuditFilterBar } from './Components/AuditFilterBar'
import { Pagination } from './Components/Pagination'
import { WorkspaceHeader } from './Components/WorkspaceHeader'
import { useStaffAuditTrail } from './hooks/use-staff-audit-trail'
import { PAGE_SIZE } from './types'

export function StaffAuditTrailPage() {
  const {
    currentUser,
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
    signOut,
    downloadingFormat,
    downloadReport,
  } = useStaffAuditTrail()

  return (
    <>
      <WorkspaceHeader currentUser={currentUser} onSignOut={signOut} />

      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-secondary-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading audit trail…" className="flex-1" />
      ) : (
        <>
          <AuditFilterBar
            dateRange={dateRange}
            onDateRangeChange={changeDateRange}
            activityType={activityType}
            onActivityTypeChange={changeActivityType}
            downloadingFormat={downloadingFormat}
            onDownload={(format) => void downloadReport(format)}
          />

          <ActivityTable entries={entries} employeeNameById={employeeNameById} />

          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </>
      )}
    </>
  )
}
