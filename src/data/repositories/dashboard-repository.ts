import type { DashboardOverview } from '../../domain/entities/dashboard-overview-schema'
import type { DashboardRecentCheckin } from '../../domain/entities/dashboard-checkin-schema'
import type { MyDashboardOverview } from '../../domain/entities/my-dashboard-overview-schema'
import type { DashboardAnalytics, DashboardRange, MyDashboardAnalytics } from '../../domain/entities/dashboard-analytics-schema'

// `branchId` narrows a branch-wide call to one branch; omitted, the API
// aggregates every branch the caller can see.
export interface DashboardBranchScope {
  branchId?: string
}

export interface DashboardRepository {
  getOverview(scope?: DashboardBranchScope): Promise<DashboardOverview>
  listRecentCheckins(options?: DashboardBranchScope & { pageSize?: number }): Promise<DashboardRecentCheckin[]>
  getAnalytics(options: DashboardBranchScope & { range: DashboardRange }): Promise<DashboardAnalytics>
  getMyOverview(): Promise<MyDashboardOverview>
  getMyAnalytics(options: { range: DashboardRange }): Promise<MyDashboardAnalytics>
}
