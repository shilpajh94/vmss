import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { VisitRequestSummary } from '../../../../domain/entities/visit-request-summary-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export const DASHBOARD_STATUS_COLUMNS = [
  { status: 'requested', label: 'Requested' },
  { status: 'approved', label: 'Approved' },
  { status: 'checked_in', label: 'Checked-in' },
  { status: 'denied', label: 'Denied' },
] as const

export function useStaffDashboard() {
  const navigate = useNavigate()
  const { listVisitRequestsUseCase, getCurrentStaffUserUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [visitRequests, setVisitRequests] = useState<VisitRequestSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [search, setSearch] = useState('')

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, requests] = await Promise.all([getCurrentStaffUserUseCase.execute(), listVisitRequestsUseCase.execute()])
      setCurrentUser(user)
      setVisitRequests(requests)
    } catch {
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listVisitRequestsUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadDashboard()
  }, [navigate, loadDashboard])

  const refresh = useCallback(() => {
    void loadDashboard()
  }, [loadDashboard])

  const signOut = useCallback(() => {
    sessionStorage.removeItem('token')
    navigate('/staff/login')
  }, [navigate])

  const filteredRequests = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return visitRequests

    return visitRequests.filter(
      (request) =>
        request.visitorName.toLowerCase().includes(query) ||
        request.hostName.toLowerCase().includes(query) ||
        request.reqId.toLowerCase().includes(query),
    )
  }, [visitRequests, search])

  const columns = useMemo(
    () =>
      DASHBOARD_STATUS_COLUMNS.map((column) => ({
        ...column,
        requests: filteredRequests.filter((request) => request.status === column.status),
      })),
    [filteredRequests],
  )

  return {
    currentUser,
    columns,
    isLoading,
    errorMessage,
    search,
    setSearch,
    refresh,
    signOut,
  }
}
