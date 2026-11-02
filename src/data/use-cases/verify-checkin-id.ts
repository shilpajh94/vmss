import type { CheckinRepository } from '../repositories/checkin-repository'

export class VerifyCheckinIdUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(visitId: string): Promise<void> {
    return this.repository.verifyId(visitId)
  }
}
