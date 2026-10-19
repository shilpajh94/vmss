import { usePageHeader } from '../../context/page-header-context'
import { BranchDashboard } from '../../components/dashboard/BranchDashboard'
import { useBranchDashboard } from '../../hooks/use-branch-dashboard'

export function AdminDashboardPage() {
  const dashboard = useBranchDashboard({ loginPath: '/admin/login' })

  usePageHeader({ description: "A bird's-eye view of today's visitor activity" })

  return <BranchDashboard dashboard={dashboard} boardBasePath="/admin/invitations" subtitle="Live visitor activity across your branches" />
}
