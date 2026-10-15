import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import type { DashboardKpi } from '../../../../domain/entities/dashboard-overview-schema'
import type { MyDashboardOverview } from '../../../../domain/entities/my-dashboard-overview-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const LOAD_ERROR = 'Something went wrong loading your dashboard. Please try again.'

// Same KPI keys as the admin dashboard so KpiRow picks the matching icons.
function buildKpis(overview: MyDashboardOverview): DashboardKpi[] {
  return [
    { key: 'visits-today', label: "Today's Visitors", value: String(overview.visitsToday) },
    { key: 'checked-in', label: 'Inside Now', value: String(overview.insideNow) },
    { key: 'pending-approval', label: 'Awaiting Approval', value: String(overview.awaitingApproval) },
    { key: 'upcoming-visitors', label: 'Upcoming Visitors', value: String(overview.upcoming) },
  ]
}

// The staff landing page: counts over the caller's own visits only
// (`GET /admin/dashboard/my-overview`), so it always agrees with their board.
export function useStaffDashboard() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getMyDashboardOverviewUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [overview, setOverview] = useState<MyDashboardOverview | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const loadOverview = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, overviewData] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          getMyDashboardOverviewUseCase.execute(),
        ])
        setCurrentUser(user)
        setOverview(overviewData)
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage(LOAD_ERROR)
        }
        toast.error(LOAD_ERROR)
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, getMyDashboardOverviewUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadOverview()
  }, [navigate, loadOverview])

  const retry = useCallback(() => {
    void loadOverview()
  }, [loadOverview])

  // Read-only dashboard: nothing to protect, so polling is never suppressed.
  usePolling(() => void loadOverview({ silent: true }), { intervalMs: 15_000, isBusy: false })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const kpis = useMemo(() => (overview ? buildKpis(overview) : []), [overview])

  const openVisit = useCallback(
    (invitationId: string) => {
      navigate(`/staff/invitations?invitationId=${encodeURIComponent(invitationId)}`)
    },
    [navigate],
  )

  return { currentUser, overview, kpis, isLoading, errorMessage, retry, openVisit }
}
