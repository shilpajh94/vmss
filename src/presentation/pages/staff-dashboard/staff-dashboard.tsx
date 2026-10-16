import { usePageHeader } from '../../context/page-header-context'
import { PersonalDashboard } from '../../components/dashboard/PersonalDashboard'
import { usePersonalDashboard } from '../../hooks/use-personal-dashboard'

export function StaffDashboardPage() {
  const dashboard = usePersonalDashboard()

  usePageHeader({ description: 'Your visitors at a glance' })

  return <PersonalDashboard dashboard={dashboard} />
}
