import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { landingPathFor } from '../../../utils/landing-path'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { DashboardOverview, DashboardKpi } from '../../../../domain/entities/dashboard-overview-schema'
import type { DashboardRecentCheckin } from '../../../../domain/entities/dashboard-checkin-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

function buildKpis(overview: DashboardOverview): DashboardKpi[] {
  return [
    { key: 'visits-today', label: "Today's Visitors", value: String(overview.visitsTodayCount) },
    { key: 'checked-in', label: 'Currently On-site', value: String(overview.checkedInCount) },
    { key: 'pending-approval', label: 'Pending Approval', value: String(overview.pendingApprovalCount) },
    { key: 'upcoming-visitors', label: 'Upcoming Visitors', value: String(overview.upcomingVisitorCount) },
  ]
}

export function useReceptionDashboard() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getDashboardOverviewUseCase, listRecentCheckinsUseCase, listHostEmployeesUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [overview, setOverview] = useState<DashboardOverview | undefined>(undefined)
  const [recentCheckins, setRecentCheckins] = useState<DashboardRecentCheckin[]>([])
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const loadOverview = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    let user: StaffUser
    try {
      user = await getCurrentStaffUserUseCase.execute()
    } catch {
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
      setIsLoading(false)
      return
    }

    if (!user.isReception) {
      navigate(landingPathFor(user), { replace: true })
      return
    }
    setCurrentUser(user)

    try {
      const [overviewData, checkins, employees] = await Promise.all([
        getDashboardOverviewUseCase.execute(),
        listRecentCheckinsUseCase.execute(),
        listHostEmployeesUseCase.execute(),
      ])
      setOverview(overviewData)
      setRecentCheckins(checkins)
      setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
    } catch {
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, getDashboardOverviewUseCase, listRecentCheckinsUseCase, listHostEmployeesUseCase, toast, navigate])

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

  const kpis = useMemo(() => (overview ? buildKpis(overview) : []), [overview])

  return {
    currentUser,
    overview,
    kpis,
    recentCheckins,
    employeeNameById,
    isLoading,
    errorMessage,
    retry,
  }
}
