import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { AuditReportFormat } from '../../../../data/repositories/audit-trail-repository'
import { DEFAULT_ACTIVITY_TYPE, DEFAULT_DATE_RANGE, PAGE_SIZE } from '../types'

const REPORT_POLL_INTERVAL_MS = 1000
const REPORT_POLL_MAX_ATTEMPTS = 20

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function useStaffAuditTrail() {
  const navigate = useNavigate()
  const { getAuditTrailUseCase, getCurrentStaffUserUseCase, listHostEmployeesUseCase, requestAuditReportUseCase, getAuditReportUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [dateRange, setDateRange] = useState(DEFAULT_DATE_RANGE)
  const [activityType, setActivityType] = useState(DEFAULT_ACTIVITY_TYPE)
  const [page, setPage] = useState(1)
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [downloadingFormat, setDownloadingFormat] = useState<AuditReportFormat | undefined>(undefined)

  const loadAuditTrail = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

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
      setEntries(response.items)
      setTotal(response.total)
      setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
    } catch {
      setErrorMessage('Something went wrong loading the audit trail. Please try again.')
      toast.error('Something went wrong loading the audit trail. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getAuditTrailUseCase, listHostEmployeesUseCase, dateRange, activityType, page, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    getCurrentStaffUserUseCase
      .execute()
      .then(setCurrentUser)
      .catch(() => {
        // The header simply omits the identity block if this fails; the page itself still works.
      })
  }, [navigate, getCurrentStaffUserUseCase])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) return
    void loadAuditTrail()
  }, [loadAuditTrail])

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

  const signOut = useCallback(() => {
    sessionStorage.removeItem('token')
    navigate('/staff/login')
  }, [navigate])

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
          const url = format === 'csv' ? job.csvDownloadUrl : job.pdfDownloadUrl
          if (url) {
            window.open(url, '_blank', 'noopener,noreferrer')
          } else {
            toast.error('The report finished but no download link was returned.')
          }
        } else if (job.status === 'failed') {
          toast.error(job.errorMessage ?? 'The report could not be generated. Please try again.')
        } else {
          toast.error('The report is taking longer than expected. Please try again shortly.')
        }
      } catch {
        toast.error('Something went wrong generating the report. Please try again.')
      } finally {
        setDownloadingFormat(undefined)
      }
    },
    [requestAuditReportUseCase, getAuditReportUseCase, dateRange, activityType, toast],
  )

  return {
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
    retry: loadAuditTrail,
    signOut,
    downloadingFormat,
    downloadReport,
  }
}
