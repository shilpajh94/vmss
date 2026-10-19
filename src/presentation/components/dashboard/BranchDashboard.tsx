import { DropdownFilter } from '../ui/DropdownFilter'
import { GitBranchIcon } from '../icons'
import { DashboardGreeting } from './DashboardGreeting'
import { DashboardLoadError, DashboardLoading } from './DashboardStates'
import { HourlyArrivalsChart } from './HourlyArrivalsChart'
import { KpiRow, type DashboardKpiTile } from './KpiRow'
import { RangeToggle } from './RangeToggle'
import { RecentCheckinsCard } from './RecentCheckinsCard'
import { StatusBarsChart } from './StatusBarsChart'
import { TopLabelsChart } from './TopLabelsChart'
import { TrafficTrendChart } from './TrafficTrendChart'
import { UpcomingVisitorsCard } from './UpcomingVisitorsCard'
import { boardStatusPath, formatWaitingSince, type BoardBasePath } from './dashboard-format'
import type { useBranchDashboard } from '../../hooks/use-branch-dashboard'
import type { DashboardOverview } from '../../../domain/entities/dashboard-overview-schema'

const ALL_BRANCHES = ''

function buildKpis(overview: DashboardOverview, basePath: BoardBasePath): DashboardKpiTile[] {
  return [
    {
      key: 'visits-today',
      label: 'Expected Today',
      value: overview.scheduledTodayCount,
      detail: `${overview.checkedInTodayCount} checked in so far`,
      href: boardStatusPath(basePath, 'approved'),
    },
    { key: 'checked-in', label: 'On-Site Now', value: overview.checkedInCount, href: boardStatusPath(basePath, 'checked_in') },
    {
      key: 'pending-approval',
      label: 'Pending Approval',
      value: overview.pendingApprovalCount,
      detail: overview.oldestPendingSubmittedAt ? `Oldest waiting ${formatWaitingSince(overview.oldestPendingSubmittedAt)}` : undefined,
      href: boardStatusPath(basePath, 'submitted'),
    },
    { key: 'upcoming-visitors', label: 'Upcoming Visitors', value: overview.upcomingVisitorCount, href: boardStatusPath(basePath, 'approved') },
  ]
}

interface BranchDashboardProps {
  dashboard: ReturnType<typeof useBranchDashboard>
  boardBasePath: BoardBasePath
  subtitle: string
}

// The branch-wide dashboard shared by admin and reception
// (dashboard-insights; shared design D11): KPI tiles, four charts, and the
// recent check-ins / upcoming visitors lists.
export function BranchDashboard({ dashboard, boardBasePath, subtitle }: BranchDashboardProps) {
  const { overview, recentCheckins, analytics, hasInitialError, isInitialLoading, retry } = dashboard

  if (hasInitialError) return <DashboardLoadError message="Something went wrong loading the dashboard. Please try again." onRetry={retry} />
  if (isInitialLoading || !overview || !recentCheckins || !analytics) return <DashboardLoading />

  const rangeDays = analytics.dailyTrend.length

  return (
    <>
      <DashboardGreeting
        firstName={dashboard.currentUser?.name.split(' ')[0]}
        subtitle={subtitle}
        today={overview.today}
        timezone={analytics.timezone}
        controls={
          <>
            {dashboard.branchOptions.length > 0 ? (
              <DropdownFilter
                icon={GitBranchIcon}
                ariaLabel="Branch"
                value={dashboard.branchId ?? ALL_BRANCHES}
                onChange={(value) => dashboard.selectBranch(value || undefined)}
                options={[{ value: ALL_BRANCHES, label: 'All branches' }, ...dashboard.branchOptions.map((branch) => ({ value: branch.id, label: branch.name }))]}
              />
            ) : null}
            <RangeToggle value={dashboard.range} onChange={dashboard.setRange} />
          </>
        }
      />

      <KpiRow kpis={buildKpis(overview, boardBasePath)} />

      <div className="grid w-full grid-cols-1 gap-4 md:gap-6 lg:grid-cols-12">
        <TrafficTrendChart
          title="Visitor Traffic"
          subtitle={`Scheduled vs. checked in · last ${rangeDays} days`}
          points={analytics.dailyTrend}
          isUpdating={dashboard.isAnalyticsLoading}
          className="lg:col-span-8"
        />
        <StatusBarsChart
          title="Visits by Status"
          statuses={analytics.statusBreakdown}
          rangeDays={rangeDays}
          boardBasePath={boardBasePath}
          isUpdating={dashboard.isAnalyticsLoading}
          className="lg:col-span-4"
        />
      </div>

      <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
        <HourlyArrivalsChart hours={analytics.hourlyCheckInsToday} timezone={analytics.timezone} />
        <TopLabelsChart
          purposes={analytics.topPurposes}
          departments={analytics.topDepartments}
          rangeDays={rangeDays}
          isUpdating={dashboard.isAnalyticsLoading}
        />
      </div>

      <div className="grid w-full grid-cols-1 gap-4 md:gap-6 lg:grid-cols-12">
        <RecentCheckinsCard checkins={recentCheckins} boardBasePath={boardBasePath} className="lg:col-span-7" />
        <UpcomingVisitorsCard
          title="Upcoming Visitors"
          subtitle="Approved and not yet arrived"
          visitors={overview.upcomingVisitors}
          boardBasePath={boardBasePath}
          showHost
          className="lg:col-span-5"
        />
      </div>
    </>
  )
}
