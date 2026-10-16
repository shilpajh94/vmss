import { DashboardGreeting } from './DashboardGreeting'
import { DashboardLoadError, DashboardLoading } from './DashboardStates'
import { KpiRow, type DashboardKpiTile } from './KpiRow'
import { RangeToggle } from './RangeToggle'
import { StatusBarsChart } from './StatusBarsChart'
import { TrafficTrendChart } from './TrafficTrendChart'
import { UpcomingVisitorsCard } from './UpcomingVisitorsCard'
import { boardStatusPath } from './dashboard-format'
import type { usePersonalDashboard } from '../../hooks/use-personal-dashboard'
import type { MyDashboardOverview } from '../../../domain/entities/my-dashboard-overview-schema'

const BOARD = '/staff/invitations'

function buildKpis(overview: MyDashboardOverview): DashboardKpiTile[] {
  return [
    { key: 'visits-today', label: 'Visits Today', value: overview.visitsToday, href: boardStatusPath(BOARD, 'approved') },
    { key: 'checked-in', label: 'Inside Now', value: overview.insideNow, href: boardStatusPath(BOARD, 'checked_in') },
    { key: 'pending-approval', label: 'Awaiting Approval', value: overview.awaitingApproval, href: boardStatusPath(BOARD, 'submitted') },
    { key: 'upcoming-visitors', label: 'Upcoming', value: overview.upcoming, href: boardStatusPath(BOARD, 'approved') },
  ]
}

// The staff landing page (staff-home-dashboard): only the visits relevant to
// the signed-in user.
export function PersonalDashboard({ dashboard }: { dashboard: ReturnType<typeof usePersonalDashboard> }) {
  const { overview, analytics, hasInitialError, isInitialLoading, retry } = dashboard

  if (hasInitialError) return <DashboardLoadError message="Something went wrong loading your dashboard. Please try again." onRetry={retry} />
  if (isInitialLoading || !overview || !analytics) return <DashboardLoading />

  const rangeDays = analytics.dailyTrend.length

  return (
    <>
      <DashboardGreeting
        firstName={dashboard.currentUser?.name.split(' ')[0]}
        subtitle="Here's how your visitors are doing."
        today={overview.today}
        timezone={analytics.timezone}
        controls={<RangeToggle value={dashboard.range} onChange={dashboard.setRange} />}
      />

      <KpiRow kpis={buildKpis(overview)} />

      <div className="grid w-full grid-cols-1 gap-4 md:gap-6 lg:grid-cols-12">
        <TrafficTrendChart
          title="My Visits"
          subtitle={`Your scheduled visits vs. arrivals · last ${rangeDays} days`}
          points={analytics.dailyTrend}
          isUpdating={dashboard.isAnalyticsLoading}
          className="lg:col-span-8"
        />
        <StatusBarsChart
          title="My Visits by Status"
          statuses={analytics.statusBreakdown}
          rangeDays={rangeDays}
          boardBasePath={BOARD}
          isUpdating={dashboard.isAnalyticsLoading}
          className="lg:col-span-4"
        />
      </div>

      <UpcomingVisitorsCard
        title="Your Upcoming Visitors"
        subtitle="Approved visits you're involved in, soonest first"
        visitors={overview.upcomingPreview}
        boardBasePath={BOARD}
        showHost={false}
      />
    </>
  )
}
