import type { DashboardRepository } from '../repositories/dashboard-repository'

export class CheckInUpcomingVisitorUseCase {
  private readonly dashboardRepository: DashboardRepository

  constructor(dashboardRepository: DashboardRepository) {
    this.dashboardRepository = dashboardRepository
  }

  async execute(id: string): Promise<void> {
    return this.dashboardRepository.checkInUpcomingVisitor(id)
  }
}
