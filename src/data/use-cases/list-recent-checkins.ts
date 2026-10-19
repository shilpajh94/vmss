import type { DashboardBranchScope, DashboardRepository } from '../repositories/dashboard-repository'
import type { DashboardRecentCheckin } from '../../domain/entities/dashboard-checkin-schema'

export class ListRecentCheckinsUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(options?: DashboardBranchScope & { pageSize?: number }): Promise<DashboardRecentCheckin[]> {
    return this.dashboardRepository.listRecentCheckins(options)
  }
}
