import type { CheckinRepository } from '../repositories/checkin-repository'

export class PrintVisitorBadgeUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(visitId: string, idempotencyKey: string): Promise<Blob> {
    return this.repository.printBadge(visitId, idempotencyKey)
  }
}
