import type { DashboardOverview } from '../../domain/entities/dashboard-overview-schema'
import type { DashboardRecentCheckin } from '../../domain/entities/dashboard-checkin-schema'

export interface DashboardRepository {
  getOverview(): Promise<DashboardOverview>
  listRecentCheckins(): Promise<DashboardRecentCheckin[]>
}
