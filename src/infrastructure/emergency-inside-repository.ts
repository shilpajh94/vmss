import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { EmergencyInsideRepository } from '../data/repositories/emergency-inside-repository'
import { EmergencyInsideResponseSchema, type EmergencyInside } from '../domain/entities/emergency-inside-schema'

export class HttpEmergencyInsideRepository implements EmergencyInsideRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  get(branchId?: string): Promise<EmergencyInside> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_EMERGENCY_INSIDE,
      headers: branchId ? { 'X-Branch-ID': branchId } : undefined,
      parserSchema: EmergencyInsideResponseSchema,
    })
  }
}
