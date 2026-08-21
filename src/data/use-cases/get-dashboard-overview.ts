import type { DashboardRepository } from '../repositories/dashboard-repository'
import type { DashboardOverview } from '../../domain/entities/dashboard-overview-schema'

export class GetDashboardOverviewUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(): Promise<DashboardOverview> {
    return this.dashboardRepository.getOverview()
  }
}
