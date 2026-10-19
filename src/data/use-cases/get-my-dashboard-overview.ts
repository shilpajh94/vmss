import type { DashboardRepository } from '../repositories/dashboard-repository'
import type { MyDashboardOverview } from '../../domain/entities/my-dashboard-overview-schema'

export class GetMyDashboardOverviewUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(): Promise<MyDashboardOverview> {
    return this.dashboardRepository.getMyOverview()
  }
}
