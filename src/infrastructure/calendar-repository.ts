import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type {
  CalendarDayPage,
  CalendarDayPageQuery,
  CalendarFeedQuery,
  CalendarRepository,
} from '../data/repositories/calendar-repository'
import { CalendarDayPageResponseSchema, CalendarFeedResponseSchema, type CalendarFeed } from '../domain/entities/calendar-feed-schema'

function statusParam(statuses: readonly string[] | undefined): readonly string[] | undefined {
  return statuses && statuses.length > 0 ? statuses : undefined
}

function branchHeader(branchId: string | undefined): Record<string, string> | undefined {
  return branchId ? { 'X-Branch-ID': branchId } : undefined
}

export class HttpCalendarRepository implements CalendarRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async getFeed({ from, to, branchId, statuses, perDayLimit }: CalendarFeedQuery): Promise<CalendarFeed> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_CALENDAR_FEED,
      queryParams: { from, to, perDayLimit, status: statusParam(statuses) },
      headers: branchHeader(branchId),
      parserSchema: CalendarFeedResponseSchema,
    })

    return response.data
  }

  async getDayPage({ date, page, pageSize, branchId, statuses }: CalendarDayPageQuery): Promise<CalendarDayPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_CALENDAR_DAY,
      queryParams: { date, page, pageSize, status: statusParam(statuses) },
      headers: branchHeader(branchId),
      parserSchema: CalendarDayPageResponseSchema,
    })

    return { events: response.data, total: response.pagination.total }
  }
}
