import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { DashboardBranchScope, DashboardRepository } from '../data/repositories/dashboard-repository'
import { DashboardOverviewResponseSchema, type DashboardOverview } from '../domain/entities/dashboard-overview-schema'
import { DashboardRecentCheckinListResponseSchema, type DashboardRecentCheckin } from '../domain/entities/dashboard-checkin-schema'
import { MyDashboardOverviewResponseSchema, type MyDashboardOverview } from '../domain/entities/my-dashboard-overview-schema'
import {
  DashboardAnalyticsResponseSchema,
  MyDashboardAnalyticsResponseSchema,
  type DashboardAnalytics,
  type DashboardRange,
  type MyDashboardAnalytics,
} from '../domain/entities/dashboard-analytics-schema'

export class HttpDashboardRepository implements DashboardRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getOverview(scope?: DashboardBranchScope): Promise<DashboardOverview> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_ADMIN_DASHBOARD_OVERVIEW,
      queryParams: { branchId: scope?.branchId },
      parserSchema: DashboardOverviewResponseSchema,
    })

    return response.data
  }

  async listRecentCheckins(options?: DashboardBranchScope & { pageSize?: number }): Promise<DashboardRecentCheckin[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_DASHBOARD_CHECKINS,
      queryParams: { branchId: options?.branchId, pageSize: options?.pageSize },
      parserSchema: DashboardRecentCheckinListResponseSchema,
    })

    return response.data
  }

  async getAnalytics({ branchId, range }: DashboardBranchScope & { range: DashboardRange }): Promise<DashboardAnalytics> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_DASHBOARD_ANALYTICS,
      queryParams: { branchId, range },
      parserSchema: DashboardAnalyticsResponseSchema,
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

  async getMyAnalytics({ range }: { range: DashboardRange }): Promise<MyDashboardAnalytics> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_MY_DASHBOARD_ANALYTICS,
      queryParams: { range },
      parserSchema: MyDashboardAnalyticsResponseSchema,
    })

    return response.data
  }
}
