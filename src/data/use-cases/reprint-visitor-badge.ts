import type { BadgeOutput } from '../../domain/entities/checkin-schema'
import type { CheckinRepository } from '../repositories/checkin-repository'

export class ReprintVisitorBadgeUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(visitId: string, reason: string): Promise<BadgeOutput> {
    return this.repository.reprintBadge(visitId, reason)
  }
}
