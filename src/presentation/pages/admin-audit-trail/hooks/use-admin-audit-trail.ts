import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'
import type { AuditReportFormat } from '../../../../data/repositories/audit-trail-repository'
import { DEFAULT_ACTIVITY_TYPE, DEFAULT_DATE_RANGE, PAGE_SIZE } from '../types'
import { saveBlob } from '../../../utils/save-blob'
import { toUserMessage } from '../../../utils/to-user-message'

const REPORT_POLL_INTERVAL_MS = 1000
const REPORT_POLL_MAX_ATTEMPTS = 20
const EMPTY_ENTRIES: AuditLogEntry[] = []
const EMPTY_NAMES: Record<string, string> = {}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function useAdminAuditTrail() {
  const {
    getAuditTrailUseCase,
    listHostEmployeesUseCase,
    requestAuditReportUseCase,
    getAuditReportUseCase,
    downloadAuditReportUseCase,
  } = useAppDependencies()
  const toast = useToast()
  const currentUser = useCurrentUser()

  const [dateRange, setDateRange] = useState(DEFAULT_DATE_RANGE)
  const [activityType, setActivityType] = useState(DEFAULT_ACTIVITY_TYPE)
  const [page, setPage] = useState(1)
  const [downloadingFormat, setDownloadingFormat] = useState<AuditReportFormat | undefined>(undefined)

  // The route already requires `audit-logs:view`. The entries are the live
  // data; employee names (for actors) load once.
  const resource = useLiveResource({
    load: () => getAuditTrailUseCase.execute({ dateRange, activityType, page, pageSize: PAGE_SIZE }),
    query: { dateRange, activityType, page },
    reference: async () =>
      Object.fromEntries((await listHostEmployeesUseCase.execute()).map((employee) => [employee.id, employee.fullName])) as Record<string, string>,
    errorMessage: 'Something went wrong loading the audit trail. Please try again.',
    isBusy: downloadingFormat !== undefined,
  })
  const { phase, isRefreshing, retry } = resource
  const entries = resource.data?.items ?? EMPTY_ENTRIES
  const total = resource.data?.total ?? 0
  const employeeNameById = resource.reference ?? EMPTY_NAMES

  const changeDateRange = useCallback((value: string) => {
    setDateRange(value)
    setPage(1)
  }, [])

  const changeActivityType = useCallback((value: string) => {
    setActivityType(value)
    setPage(1)
  }, [])

  const goToNextPage = useCallback(() => setPage((prev) => prev + 1), [])
  const goToPrevPage = useCallback(() => setPage((prev) => Math.max(1, prev - 1)), [])

  const downloadReport = useCallback(
    async (format: AuditReportFormat) => {
      setDownloadingFormat(format)

      try {
        let job = await requestAuditReportUseCase.execute({ dateRange, activityType }, [format])

        for (let attempt = 0; job.status === 'pending' && attempt < REPORT_POLL_MAX_ATTEMPTS; attempt += 1) {
          await wait(REPORT_POLL_INTERVAL_MS)
          job = await getAuditReportUseCase.execute(job.id)
        }

        if (job.status === 'ready') {
          const hasFormat = format === 'csv' ? job.csvDownloadUrl !== null : job.pdfDownloadUrl !== null
          if (!hasFormat) {
            toast.error('The report finished but no download link was returned.')
            return
          }

          try {
            const blob = await downloadAuditReportUseCase.execute(job.id, format)
            saveBlob(blob, `audit-report.${format}`)
          } catch (error) {
            toast.error(toUserMessage(error, 'Something went wrong downloading the report. Please try again.'))
          }
        } else if (job.status === 'failed') {
          toast.error(job.errorMessage ?? 'The report could not be generated. Please try again.')
        } else {
          toast.error('The report is taking longer than expected. Please try again shortly.')
        }
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong generating the report. Please try again.'))
      } finally {
        setDownloadingFormat(undefined)
      }
    },
    [requestAuditReportUseCase, getAuditReportUseCase, downloadAuditReportUseCase, dateRange, activityType, toast],
  )

  return {
    currentUser,
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
  }
}
