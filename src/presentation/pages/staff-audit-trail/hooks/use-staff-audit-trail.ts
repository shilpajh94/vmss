import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'
import type { AuditTrailStats } from '../../../../domain/entities/audit-trail-response-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { DEFAULT_ACTIVITY_TYPE, DEFAULT_DATE_RANGE, PAGE_SIZE } from '../types'

const SEARCH_DEBOUNCE_MS = 300

export function useStaffAuditTrail() {
  const navigate = useNavigate()
  const { getAuditTrailUseCase, getCurrentStaffUserUseCase } = useAppDependencies()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [dateRange, setDateRange] = useState(DEFAULT_DATE_RANGE)
  const [activityType, setActivityType] = useState(DEFAULT_ACTIVITY_TYPE)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<AuditTrailStats | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [searchInput])

  const loadAuditTrail = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const response = await getAuditTrailUseCase.execute({
        dateRange,
        activityType,
        search: debouncedSearch,
        page,
        pageSize: PAGE_SIZE,
      })
      setEntries(response.items)
      setTotal(response.total)
      setStats(response.stats)
    } catch {
      setErrorMessage('Something went wrong loading the audit trail. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getAuditTrailUseCase, dateRange, activityType, debouncedSearch, page])

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

  const changeSearch = useCallback((value: string) => {
    setSearchInput(value)
    setPage(1)
  }, [])

  const goToNextPage = useCallback(() => setPage((prev) => prev + 1), [])
  const goToPrevPage = useCallback(() => setPage((prev) => Math.max(1, prev - 1)), [])

  const signOut = useCallback(() => {
    sessionStorage.removeItem('token')
    navigate('/staff/login')
  }, [navigate])

  return {
    currentUser,
    dateRange,
    activityType,
    search: searchInput,
    page,
    entries,
    total,
    stats,
    isLoading,
    errorMessage,
    changeDateRange,
    changeActivityType,
    changeSearch,
    goToNextPage,
    goToPrevPage,
    retry: loadAuditTrail,
    signOut,
  }
}
