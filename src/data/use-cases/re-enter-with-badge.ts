import type { CheckinRepository } from '../repositories/checkin-repository'
import type { BadgeScanResult } from '../../domain/entities/checkin-schema'

export class ReEnterWithBadgeUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(token: string): Promise<BadgeScanResult> {
    return this.repository.reEnterWithBadge(token)
  }
}
