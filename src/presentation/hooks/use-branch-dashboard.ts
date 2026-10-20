import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useCurrentUser } from '../context/current-user-context'
import { useBranchOptions } from './use-branch-options'
import { useLiveDashboard, useLiveResource } from './use-live-dashboard'
import type { DashboardRange } from '../../domain/entities/dashboard-analytics-schema'

const LOAD_ERROR = 'Something went wrong loading the dashboard. Please try again.'
const RECENT_CHECKINS_PAGE_SIZE = 8

interface UseBranchDashboardOptions {
  loginPath: string
  // False while the page is still deciding whether the user may see it
  // (reception's role guard) — nothing is fetched until it's true.
  allowed?: boolean
}

// Data for the branch-wide dashboards (admin and reception): overview,
// recent check-ins and analytics, each re-fetched on its own key so a range
// switch reloads only the charts (dashboard-insights "Range Toggle").
export function useBranchDashboard({ loginPath, allowed = true }: UseBranchDashboardOptions) {
  const navigate = useNavigate()
  const currentUser = useCurrentUser()
  const { getDashboardOverviewUseCase, listRecentCheckinsUseCase, getDashboardAnalyticsUseCase } = useAppDependencies()

  const [range, setRange] = useState<DashboardRange>('7d')
  const [branchId, setBranchId] = useState<string | undefined>(undefined)

  useEffect(() => {
    if (!sessionStorage.getItem('token')) navigate(loginPath, { replace: true })
  }, [navigate, loginPath])

  const enabled = allowed

  const overview = useLiveResource(() => getDashboardOverviewUseCase.execute({ branchId }), `overview:${branchId ?? 'all'}`, enabled)
  const recentCheckins = useLiveResource(
    () => listRecentCheckinsUseCase.execute({ branchId, pageSize: RECENT_CHECKINS_PAGE_SIZE }),
    `checkins:${branchId ?? 'all'}`,
    enabled,
  )
  const analytics = useLiveResource(
    () => getDashboardAnalyticsUseCase.execute({ branchId, range }),
    `analytics:${branchId ?? 'all'}:${range}`,
    enabled,
  )

  const live = useLiveDashboard([overview, recentCheckins, analytics], LOAD_ERROR, enabled)

  const branchOptions = useBranchOptions(currentUser, allowed)

  const selectBranch = useCallback((id: string | undefined) => setBranchId(id), [])

  return {
    currentUser,
    overview: overview.data,
    recentCheckins: recentCheckins.data,
    analytics: analytics.data,
    // Only while a newly chosen range is loading — not on every background poll.
    isAnalyticsLoading: analytics.data !== undefined && analytics.data.range !== range,
    range,
    setRange,
    branchId,
    selectBranch,
    branchOptions,
    ...live,
  }
}
