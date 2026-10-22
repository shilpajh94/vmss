import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { landingPathFor } from '../../../utils/landing-path'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { AuditReportFormat } from '../../../../data/repositories/audit-trail-repository'
import { DEFAULT_ACTIVITY_TYPE, DEFAULT_DATE_RANGE, PAGE_SIZE } from '../types'
import { saveBlob } from '../../../utils/save-blob'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import { toUserMessage } from '../../../utils/to-user-message'
import { permissionsFor } from '../../../utils/permissions'

const REPORT_POLL_INTERVAL_MS = 1000
const REPORT_POLL_MAX_ATTEMPTS = 20

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function useAdminAuditTrail() {
  const navigate = useNavigate()
  const {
    getAuditTrailUseCase,
    getCurrentStaffUserUseCase,
    listHostEmployeesUseCase,
    requestAuditReportUseCase,
    getAuditReportUseCase,
    downloadAuditReportUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [dateRange, setDateRange] = useState(DEFAULT_DATE_RANGE)
  const [activityType, setActivityType] = useState(DEFAULT_ACTIVITY_TYPE)
  const [page, setPage] = useState(1)
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [downloadingFormat, setDownloadingFormat] = useState<AuditReportFormat | undefined>(undefined)

  // Admins only: confirm the signed-in user's admin status before loading any
  // audit data, redirecting a non-admin authenticated user back to their own
  // dashboard instead of rendering this page.
  // Initial load, filter/page change and retry are `user` loads: once rows
  // exist they stay on screen with a progress cue. The 10s poll is a
  // `background` load: no cue, and a failure keeps the last rows without a
  // toast (the next poll retries).
  const load = useCallback(async (mode: LoadMode = 'user') => {
    const request = begin(mode)

    let user: StaffUser
    try {
      user = await getCurrentStaffUserUseCase.execute()
    } catch {
      if (!request.fail() || (mode === 'background' && !request.isInitial)) return
      toast.error('Something went wrong loading the audit trail. Please try again.')
      return
    }

    // The route already requires `audit-logs:view`; this only covers a
    // permission revoked while the page is open.
    if (!permissionsFor(user).can('audit-logs:view')) {
      navigate(landingPathFor(user), { replace: true })
      return
    }
    setCurrentUser(user)

    try {
      const [response, employees] = await Promise.all([
        getAuditTrailUseCase.execute({
          dateRange,
          activityType,
          page,
          pageSize: PAGE_SIZE,
        }),
        listHostEmployeesUseCase.execute(),
      ])
      if (!request.succeed()) return
      setEntries(response.items)
      setTotal(response.total)
      setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
    } catch {
      if (!request.fail() || (mode === 'background' && !request.isInitial)) return
      toast.error('Something went wrong loading the audit trail. Please try again.')
    }
  }, [begin, getCurrentStaffUserUseCase, getAuditTrailUseCase, listHostEmployeesUseCase, dateRange, activityType, page, toast, navigate])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  usePolling(() => void load('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: downloadingFormat !== undefined })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

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
