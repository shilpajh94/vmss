import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { HostSearchRepository } from '../data/repositories/host-search-repository'
import { HostSearchEnvelopeSchema, type HostSearchResultOut } from '../domain/entities/host-search-out-schema'
import type { HostSearchResult } from '../domain/entities/host-search-schema'

function toHostSearchResult(host: HostSearchResultOut): HostSearchResult {
  return {
    id: host.id,
    name: host.name,
    email: host.email,
    department: host.department ?? undefined,
  }
}

export class HttpHostSearchRepository implements HostSearchRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async search(query: string, limit?: number): Promise<HostSearchResult[]> {
    const envelope = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.SEARCH_HOSTS,
      queryParams: { query, limit },
      parserSchema: HostSearchEnvelopeSchema,
    })

    return envelope.data.hosts.map(toHostSearchResult)
  }
}
