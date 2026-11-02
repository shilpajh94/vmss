import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { usePageHeader } from '../../context/page-header-context'
import { useCurrentUser } from '../../context/current-user-context'
import { BranchDashboard } from '../../components/dashboard/BranchDashboard'
import { DashboardLoading } from '../../components/dashboard/DashboardStates'
import { useBranchDashboard } from '../../hooks/use-branch-dashboard'
import { landingPathFor } from '../../utils/landing-path'

// Rendered inside StaffLayout, which supplies the Reception sidebar, the
// "Reception Desk" top bar and its refresh control (reception-dashboard
// "Page renders the Reception sidebar and top bar").
export function ReceptionDashboardPage() {
  const navigate = useNavigate()
  const currentUser = useCurrentUser()
  const isReception = currentUser?.isReception === true
  const dashboard = useBranchDashboard({ allowed: isReception })

  usePageHeader({ description: "A bird's-eye view of today's visitor activity" })

  // Role guard: anyone without the Reception role goes to their own landing page.
  useEffect(() => {
    if (currentUser && !currentUser.isReception) navigate(landingPathFor(currentUser), { replace: true })
  }, [currentUser, navigate])

  if (!isReception) return <DashboardLoading />

  return <BranchDashboard dashboard={dashboard} boardBasePath="/staff/invitations" subtitle="Live visitor activity at your desk" />
}
