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

// Maps raw API `status` values to the columns above.
// TODO: only "submitted" -> "requested" is confirmed against real API data so far;
// the approved/checked_in/denied wire values still need verifying against the backend.
const STATUS_ALIASES: Record<string, (typeof DASHBOARD_STATUS_COLUMNS)[number]['status']> = {
  submitted: 'requested',
}

function normalizeStatus(status: string): string {
  return STATUS_ALIASES[status] ?? status
}

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
    } catch (error) {
      console.error('Failed to load dashboard', error)
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listVisitRequestsUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadDashboard()
  }, [navigate, loadDashboard])

  const refresh = useCallback(() => {
    void loadDashboard()
  }, [loadDashboard])

  const signOut = useCallback(() => {
    sessionStorage.removeItem('token')
    navigate('/admin/login')
  }, [navigate])

  const filteredRequests = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return visitRequests

    return visitRequests.filter(
      (request) =>
        request.primaryContactFullName.toLowerCase().includes(query) ||
        request.trackingId.toLowerCase().includes(query),
    )
  }, [visitRequests, search])

  const columns = useMemo(
    () =>
      DASHBOARD_STATUS_COLUMNS.map((column) => ({
        ...column,
        requests: filteredRequests.filter((request) => normalizeStatus(request.status) === column.status),
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
