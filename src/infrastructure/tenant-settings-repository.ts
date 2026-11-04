import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { TenantSettingsRepository } from '../data/repositories/tenant-settings-repository'
import { TenantMeResponseSchema, TenantSettingsResponseSchema } from '../domain/entities/checkin-schema'

export class HttpTenantSettingsRepository implements TenantSettingsRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getBadgePrintFlowEnabled(): Promise<boolean> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_TENANT_ME,
      parserSchema: TenantMeResponseSchema,
    })

    return response.data.badgePrintFlowEnabled
  }

  async getZoneAccessEnabled(): Promise<boolean> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_TENANT_ME,
      parserSchema: TenantMeResponseSchema,
    })

    return response.data.zoneAccessEnabled
  }

  async setZoneAccessEnabled(enabled: boolean): Promise<void> {
    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_TENANT_SETTINGS,
      body: { zoneAccessEnabled: enabled },
      parserSchema: TenantSettingsResponseSchema,
    })
  }

  async setBadgePrintFlowEnabled(enabled: boolean): Promise<void> {
    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_TENANT_SETTINGS,
      body: { badgePrintFlowEnabled: enabled },
      parserSchema: TenantSettingsResponseSchema,
    })
  }
}
