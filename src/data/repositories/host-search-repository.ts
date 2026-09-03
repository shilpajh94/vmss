import type { HostSearchResult } from '../../domain/entities/host-search-schema'

export interface HostSearchRepository {
  search(query: string, limit?: number): Promise<HostSearchResult[]>
}
