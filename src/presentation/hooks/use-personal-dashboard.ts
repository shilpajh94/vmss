import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useCurrentUser } from '../context/current-user-context'
import { useLiveDashboard, useLiveResource } from './use-live-dashboard'
import type { DashboardRange } from '../../domain/entities/dashboard-analytics-schema'

const LOAD_ERROR = 'Something went wrong loading your dashboard. Please try again.'

// The staff landing page: counts and charts over the caller's own visits only
// (`my-overview` / `my-analytics`), so it always agrees with their board.
export function usePersonalDashboard() {
  const navigate = useNavigate()
  const currentUser = useCurrentUser()
  const { getMyDashboardOverviewUseCase, getMyDashboardAnalyticsUseCase } = useAppDependencies()
  const [range, setRange] = useState<DashboardRange>('7d')

  useEffect(() => {
    if (!sessionStorage.getItem('token')) navigate('/staff/login', { replace: true })
  }, [navigate])

  const enabled = true
  const overview = useLiveResource(() => getMyDashboardOverviewUseCase.execute(), 'my-overview', enabled)
  const analytics = useLiveResource(() => getMyDashboardAnalyticsUseCase.execute({ range }), `my-analytics:${range}`, enabled)
  const live = useLiveDashboard([overview, analytics], LOAD_ERROR, enabled)

  return {
    currentUser,
    overview: overview.data,
    analytics: analytics.data,
    // Only while a newly chosen range is loading — not on every background poll.
    isAnalyticsLoading: analytics.data !== undefined && analytics.data.range !== range,
    range,
    setRange,
    ...live,
  }
}
