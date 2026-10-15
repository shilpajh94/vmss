import type { DashboardOverview } from '../../domain/entities/dashboard-overview-schema'
import type { DashboardRecentCheckin } from '../../domain/entities/dashboard-checkin-schema'
import type { MyDashboardOverview } from '../../domain/entities/my-dashboard-overview-schema'

export interface DashboardRepository {
  getOverview(): Promise<DashboardOverview>
  listRecentCheckins(): Promise<DashboardRecentCheckin[]>
  getMyOverview(): Promise<MyDashboardOverview>
}
