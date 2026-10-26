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
import { VISIT_DAY_STATUSES, boardDrillDownPath, formatWaitingSince, type BoardBasePath } from './dashboard-format'
import type { useBranchDashboard } from '../../hooks/use-branch-dashboard'
import type { DashboardOverview } from '../../../domain/entities/dashboard-overview-schema'

const ALL_BRANCHES = ''

// Each tile links to exactly what it counts (dashboard-insights "KPI Tiles
// Link to the Matching Invitations"), narrowed to the selected branch.
function buildKpis(overview: DashboardOverview, basePath: BoardBasePath, branchId: string | undefined): DashboardKpiTile[] {
  const link = (drillDown: Parameters<typeof boardDrillDownPath>[1]) => boardDrillDownPath(basePath, { ...drillDown, branchId })
  return [
    {
      key: 'visits-today',
      label: 'Expected Today',
      value: overview.scheduledTodayCount,
      detail: `${overview.scheduledTodayCheckedInCount} checked in so far`,
      href: link({ statuses: VISIT_DAY_STATUSES, visitDateFrom: overview.today, visitDateTo: overview.today }),
    },
    { key: 'checked-in', label: 'On-Site Now', value: overview.checkedInCount, href: link({ statuses: ['checked_in'] }) },
    {
      key: 'pending-approval',
      label: 'Pending Approval',
      value: overview.openPendingApprovalCount,
      detail: overview.oldestOpenPendingSubmittedAt ? `Oldest waiting ${formatWaitingSince(overview.oldestOpenPendingSubmittedAt)}` : undefined,
      href: link({ statuses: ['submitted'], excludeExpired: true }),
    },
    { key: 'upcoming-visitors', label: 'Upcoming Visitors', value: overview.upcomingVisitorCount, href: link({ upcoming: true }) },
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

      <KpiRow kpis={buildKpis(overview, boardBasePath, dashboard.branchId)} />

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
          visitDateFrom={analytics.dailyTrend[0]?.date ?? analytics.today}
          visitDateTo={analytics.today}
          branchId={dashboard.branchId}
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
        <RecentCheckinsCard checkins={recentCheckins} boardBasePath={boardBasePath} branchId={dashboard.branchId} className="lg:col-span-7" />
        <UpcomingVisitorsCard
          title="Upcoming Visitors"
          subtitle="Approved and not yet arrived"
          visitors={overview.upcomingVisitors}
          boardBasePath={boardBasePath}
          branchId={dashboard.branchId}
          showHost
          className="lg:col-span-5"
        />
      </div>
    </>
  )
}
