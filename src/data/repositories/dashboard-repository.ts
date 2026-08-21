import type { DashboardOverview } from '../../domain/entities/dashboard-overview-schema'

export interface DashboardRepository {
  getOverview(): Promise<DashboardOverview>
  checkInUpcomingVisitor(id: string): Promise<void>
}
