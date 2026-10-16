import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useCurrentUser } from '../context/current-user-context'
import { useLiveDashboard, useLiveResource } from './use-live-dashboard'
import type { DashboardRange } from '../../domain/entities/dashboard-analytics-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

const LOAD_ERROR = 'Something went wrong loading the dashboard. Please try again.'
const RECENT_CHECKINS_PAGE_SIZE = 8
// Roles that see branch-wide invitations (`invitations:view-all`).
const BRANCH_WIDE_ROLES = new Set(['admin', 'reception', 'security'])

export interface BranchOption {
  id: string
  name: string
}

// Branch ids the user can scope the dashboard to: undefined means every
// branch (a company-wide grant), otherwise the explicit set.
function authorizedBranchIds(user: StaffUser): Set<string> | undefined {
  const grants = user.branchRoles.filter((grant) => BRANCH_WIDE_ROLES.has(grant.roleName.toLowerCase()))
  if (grants.some((grant) => grant.branchId === null)) return undefined
  return new Set(grants.map((grant) => grant.branchId).filter((id): id is string => id !== null))
}

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
  const { getDashboardOverviewUseCase, listRecentCheckinsUseCase, getDashboardAnalyticsUseCase, listBranchesUseCase } = useAppDependencies()

  const [range, setRange] = useState<DashboardRange>('7d')
  const [branchId, setBranchId] = useState<string | undefined>(undefined)
  const [branchOptions, setBranchOptions] = useState<BranchOption[]>([])

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

  // Branch names come from the public branch list, narrowed to the ones the
  // user holds a branch-wide role at. Only offered when there's a choice.
  useEffect(() => {
    if (!currentUser || !allowed) return
    const authorized = authorizedBranchIds(currentUser)
    if (authorized !== undefined && authorized.size < 2) {
      setBranchOptions([])
      return
    }
    let isCurrent = true
    listBranchesUseCase
      .execute()
      .then((branches) => {
        if (!isCurrent) return
        setBranchOptions(
          branches
            .filter((branch) => authorized === undefined || authorized.has(branch.id))
            .map((branch) => ({ id: branch.id, name: branch.name })),
        )
      })
      .catch((error: unknown) => {
        // The selector is an enhancement; the dashboard works without it.
        console.error('Failed to load branches for the dashboard selector', error)
      })
    return () => {
      isCurrent = false
    }
  }, [currentUser, allowed, listBranchesUseCase])

  const selectBranch = useCallback((id: string | undefined) => setBranchId(id), [])

  const branchSelectOptions = useMemo(() => (branchOptions.length > 1 ? branchOptions : []), [branchOptions])

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
    branchOptions: branchSelectOptions,
    ...live,
  }
}
