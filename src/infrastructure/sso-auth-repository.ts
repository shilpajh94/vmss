import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { SsoAuthRepository } from '../data/repositories/sso-auth-repository'
import { SsoExchangeResponseSchema, type SsoExchangeResponse, type SsoExchangeResult } from '../domain/entities/sso-exchange-schema'

export class HttpSsoAuthRepository implements SsoAuthRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  startLoginUrl(tenantSlug: string): string {
    const path = API_ENDPOINTS.START_SSO_LOGIN.endpoint.replace(':tenantSlug', encodeURIComponent(tenantSlug))
    return `${this.apiClient.getBaseUrl()}${path}`
  }

  async exchange(code: string): Promise<SsoExchangeResult> {
    const response = await this.apiClient.makeRequest<SsoExchangeResponse>({
      endpointConfig: API_ENDPOINTS.SSO_EXCHANGE,
      body: { code },
      parserSchema: SsoExchangeResponseSchema,
    })

    return { token: response.data.accessToken }
  }
}
