import type { DashboardBranchScope, DashboardRepository } from '../repositories/dashboard-repository'
import type { DashboardAnalytics, DashboardRange } from '../../domain/entities/dashboard-analytics-schema'

export class GetDashboardAnalyticsUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(options: DashboardBranchScope & { range: DashboardRange }): Promise<DashboardAnalytics> {
    return this.dashboardRepository.getAnalytics(options)
  }
}
