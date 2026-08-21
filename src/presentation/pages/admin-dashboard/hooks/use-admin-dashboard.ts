import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { DashboardOverview } from '../../../../domain/entities/dashboard-overview-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

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
      const [user, overviewData] = await Promise.all([getCurrentStaffUserUseCase.execute(), getDashboardOverviewUseCase.execute()])
      setCurrentUser(user)
      setOverview(overviewData)
    } catch {
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, getDashboardOverviewUseCase, toast])

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
