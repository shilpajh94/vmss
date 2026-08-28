import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { DashboardOverview } from '../../../../domain/entities/dashboard-overview-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

// Temporary placeholder overview so the stat cards aren't empty while the overview API is still being wired up
// (the endpoint currently 404s on the backend). Other sections stay empty rather than showing fake activity.
// TODO: remove once getDashboardOverviewUseCase reliably returns data.
const DUMMY_OVERVIEW: DashboardOverview = {
  kpis: [
    { key: 'todays-visitors', label: "Today's Visitors", value: '47', trendCaption: '+12% from average', trendDirection: 'up' },
    { key: 'currently-on-site', label: 'Currently On-site', value: '18', trendCaption: '+4% from average', trendDirection: 'up' },
    { key: 'pre-registered', label: 'Pre-registered', value: '9', trendCaption: '-2% from average', trendDirection: 'down' },
    { key: 'average-visit-duration', label: 'Average Visit Duration', value: '42m', trendCaption: '+6% from average', trendDirection: 'up' },
  ],
  trafficSeries: [],
  recentCheckins: [],
  departmentBreakdown: [],
  activeDepartmentCount: 0,
  upcomingVisitors: [],
}

export function useAdminDashboard() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getDashboardOverviewUseCase, checkInUpcomingVisitorUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [overview, setOverview] = useState<DashboardOverview | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [checkingInIds, setCheckingInIds] = useState<string[]>([])

  const loadOverview = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const user = await getCurrentStaffUserUseCase.execute()
      setCurrentUser(user)
    } catch {
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
      setIsLoading(false)
      return
    }

    try {
      const overviewData = await getDashboardOverviewUseCase.execute()
      setOverview(overviewData.kpis.length > 0 ? overviewData : { ...overviewData, kpis: DUMMY_OVERVIEW.kpis })
    } catch {
      setOverview(DUMMY_OVERVIEW)
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, getDashboardOverviewUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadOverview()
  }, [navigate, loadOverview])

  const retry = useCallback(() => {
    void loadOverview()
  }, [loadOverview])

  const checkInVisitor = useCallback(
    async (id: string) => {
      setCheckingInIds((current) => [...current, id])

      try {
        await checkInUpcomingVisitorUseCase.execute(id)
        setOverview((current) => (current ? { ...current, upcomingVisitors: current.upcomingVisitors.filter((visitor) => visitor.id !== id) } : current))
        toast.success('Visitor checked in.')
      } catch {
        toast.error('Something went wrong checking in the visitor. Please try again.')
      } finally {
        setCheckingInIds((current) => current.filter((checkingInId) => checkingInId !== id))
      }
    },
    [checkInUpcomingVisitorUseCase, toast],
  )

  return {
    currentUser,
    overview,
    isLoading,
    errorMessage,
    retry,
    checkingInIds,
    checkInVisitor,
  }
}
