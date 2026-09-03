import type { HostSearchRepository } from '../repositories/host-search-repository'
import type { HostSearchResult } from '../../domain/entities/host-search-schema'

export class SearchHostsUseCase {
  private readonly hostSearchRepository: HostSearchRepository

  constructor(hostSearchRepository: HostSearchRepository) {
    this.hostSearchRepository = hostSearchRepository
  }

  async execute(query: string, limit?: number): Promise<HostSearchResult[]> {
    return this.hostSearchRepository.search(query, limit)
  }
}
