import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { DashboardRepository } from '../data/repositories/dashboard-repository'
import { DashboardOverviewSchema, type DashboardOverview } from '../domain/entities/dashboard-overview-schema'

export class HttpDashboardRepository implements DashboardRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getOverview(): Promise<DashboardOverview> {
    return this.apiClient.makeRequest<DashboardOverview>({
      endpointConfig: API_ENDPOINTS.GET_ADMIN_DASHBOARD_OVERVIEW,
      parserSchema: DashboardOverviewSchema,
    })
  }

  async checkInUpcomingVisitor(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.CHECK_IN_UPCOMING_VISITOR,
      queryParams: { id },
      parserSchema: z.unknown(),
    })
  }
}
