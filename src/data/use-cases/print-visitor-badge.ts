import type { BadgeOutput } from '../../domain/entities/checkin-schema'
import type { CheckinRepository } from '../repositories/checkin-repository'

export class PrintVisitorBadgeUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(visitId: string): Promise<BadgeOutput> {
    return this.repository.printBadge(visitId)
  }
}
