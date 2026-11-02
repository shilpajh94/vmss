import type { CheckinRepository } from '../repositories/checkin-repository'
import type { CheckinSearchPage } from '../../domain/entities/checkin-schema'

export class SearchCheckinVisitsUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(params: { q: string; page: number; pageSize: number }): Promise<CheckinSearchPage> {
    return this.repository.search(params)
  }
}
