import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { KioskLocationValidationRepository } from '../data/repositories/kiosk-location-validation-repository'
import { KioskLocationValidationResponseSchema } from '../domain/entities/kiosk-location-validation-schema'

export class HttpKioskLocationValidationRepository implements KioskLocationValidationRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async get(): Promise<boolean> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_KIOSK_LOCATION_VALIDATION,
      parserSchema: KioskLocationValidationResponseSchema,
    })

    return response.data.enforceKioskLocationValidation
  }

  async set(enforce: boolean): Promise<boolean> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_KIOSK_LOCATION_VALIDATION,
      body: { enforceKioskLocationValidation: enforce },
      parserSchema: KioskLocationValidationResponseSchema,
    })

    return response.data.enforceKioskLocationValidation
  }
}
