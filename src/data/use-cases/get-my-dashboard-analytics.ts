import type { DashboardRepository } from '../repositories/dashboard-repository'
import type { DashboardRange, MyDashboardAnalytics } from '../../domain/entities/dashboard-analytics-schema'

export class GetMyDashboardAnalyticsUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(options: { range: DashboardRange }): Promise<MyDashboardAnalytics> {
    return this.dashboardRepository.getMyAnalytics(options)
  }
}
