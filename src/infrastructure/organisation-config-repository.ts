import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { OrganisationConfigRepository } from '../data/repositories/organisation-config-repository'
import { OrganisationConfigSchema, type OrganisationConfig } from '../domain/entities/organisation-config-schema'
import { UploadResponseSchema, type UploadResponse } from '../domain/entities/upload-response-schema'

export class HttpOrganisationConfigRepository implements OrganisationConfigRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async get(): Promise<OrganisationConfig> {
    return this.apiClient.makeRequest<OrganisationConfig>({
      endpointConfig: API_ENDPOINTS.GET_ORGANISATION_CONFIG,
      parserSchema: OrganisationConfigSchema,
    })
  }

  async update(config: OrganisationConfig): Promise<OrganisationConfig> {
    return this.apiClient.makeRequest<OrganisationConfig>({
      endpointConfig: API_ENDPOINTS.UPDATE_ORGANISATION_CONFIG,
      body: config,
      parserSchema: OrganisationConfigSchema,
    })
  }

  async uploadLogo(file: File): Promise<UploadResponse> {
    return this.apiClient.uploadFile<UploadResponse>({
      endpointConfig: API_ENDPOINTS.UPLOAD_ORGANISATION_LOGO,
      file,
      parserSchema: UploadResponseSchema,
    })
  }
}
