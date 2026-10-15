import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { DashboardRepository } from '../data/repositories/dashboard-repository'
import { DashboardOverviewResponseSchema, type DashboardOverview } from '../domain/entities/dashboard-overview-schema'
import { DashboardRecentCheckinListResponseSchema, type DashboardRecentCheckin } from '../domain/entities/dashboard-checkin-schema'
import { MyDashboardOverviewResponseSchema, type MyDashboardOverview } from '../domain/entities/my-dashboard-overview-schema'

export class HttpDashboardRepository implements DashboardRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getOverview(): Promise<DashboardOverview> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_ADMIN_DASHBOARD_OVERVIEW,
      parserSchema: DashboardOverviewResponseSchema,
    })

    return response.data
  }

  async listRecentCheckins(): Promise<DashboardRecentCheckin[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_DASHBOARD_CHECKINS,
      parserSchema: DashboardRecentCheckinListResponseSchema,
    })

    return response.data
  }

  async getMyOverview(): Promise<MyDashboardOverview> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_MY_DASHBOARD_OVERVIEW,
      parserSchema: MyDashboardOverviewResponseSchema,
    })

    return response.data
  }
}
