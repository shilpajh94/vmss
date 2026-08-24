import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { OrganisationConfigRepository } from '../data/repositories/organisation-config-repository'
import { CompanyResponseSchema, type Company } from '../domain/entities/company-schema'
import type { OrganisationConfig } from '../domain/entities/organisation-config-schema'

const BADGE_EXPIRY_MINUTES_BY_DURATION: Record<string, number> = {
  '4h': 240,
  '8h': 480,
  '12h': 720,
  '24h': 1440,
}

const DEFAULT_BADGE_EXPIRY_DURATION = '8h'
const DEFAULT_TIMEZONE = 'GMT+00:00'

function toBadgeExpiryDuration(minutes: number | null): string {
  const match = Object.entries(BADGE_EXPIRY_MINUTES_BY_DURATION).find(([, value]) => value === minutes)
  return match?.[0] ?? DEFAULT_BADGE_EXPIRY_DURATION
}

function toOrganisationConfig(company: Company): OrganisationConfig {
  return {
    organisationName: company.legalName,
    logoUrl: company.logoUrl ?? undefined,
    defaultTimezone: company.defaultTimezone ?? DEFAULT_TIMEZONE,
    autoApprovePreRegistered: company.autoApprovePreRegisteredVisitors,
    passBadgeExpiryDuration: toBadgeExpiryDuration(company.badgeExpiryDurationMinutes),
  }
}

export class HttpOrganisationConfigRepository implements OrganisationConfigRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async get(): Promise<OrganisationConfig> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_ORGANISATION_CONFIG,
      parserSchema: CompanyResponseSchema,
    })

    return toOrganisationConfig(response.data)
  }

  async update(config: OrganisationConfig): Promise<OrganisationConfig> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_ORGANISATION_CONFIG,
      body: {
        legalName: config.organisationName,
        logoUrl: config.logoUrl ?? null,
        defaultTimezone: config.defaultTimezone,
        autoApprovePreRegisteredVisitors: config.autoApprovePreRegistered,
        badgeExpiryDurationMinutes: BADGE_EXPIRY_MINUTES_BY_DURATION[config.passBadgeExpiryDuration] ?? null,
      },
      parserSchema: CompanyResponseSchema,
    })

    return toOrganisationConfig(response.data)
  }
}
