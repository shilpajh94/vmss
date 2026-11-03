import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { CheckinRepository } from '../data/repositories/checkin-repository'
import {
  BadgeScanResponseSchema,
  CheckinPhotoResponseSchema,
  CheckinSearchResponseSchema,
  CheckinVerifyIdResponseSchema,
  type BadgeScanResult,
  type CheckinSearchPage,
  type CheckinSearchRow,
} from '../domain/entities/checkin-schema'

export class HttpCheckinRepository implements CheckinRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async search({ q, page, pageSize }: { q: string; page: number; pageSize: number }): Promise<CheckinSearchPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CHECKIN_SEARCH,
      queryParams: { q, page, pageSize },
      parserSchema: CheckinSearchResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async verifyId(visitId: string): Promise<void> {
    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CHECKIN_VERIFY_ID,
      pathParams: { visitId },
      parserSchema: CheckinVerifyIdResponseSchema,
    })
  }

  async uploadPhoto(visitId: string, file: File): Promise<CheckinSearchRow> {
    const response = await this.apiClient.uploadFile({
      endpointConfig: API_ENDPOINTS.CHECKIN_UPLOAD_PHOTO,
      pathParams: { visitId },
      file,
      parserSchema: CheckinPhotoResponseSchema,
    })

    return response.data
  }

  async printBadge(visitId: string): Promise<Blob> {
    return this.apiClient.downloadBlob({
      endpointConfig: API_ENDPOINTS.CHECKIN_PRINT_BADGE,
      pathParams: { visitId },
    })
  }

  async reprintBadge(visitId: string, reason: string): Promise<Blob> {
    return this.apiClient.downloadBlob({
      endpointConfig: API_ENDPOINTS.CHECKIN_REPRINT_BADGE,
      pathParams: { visitId },
      queryParams: { reason },
    })
  }

  async checkOutWithBadge(token: string): Promise<BadgeScanResult> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CHECKIN_BADGE_CHECK_OUT,
      body: { token },
      parserSchema: BadgeScanResponseSchema,
    })
  }

  async checkInWithBadge(token: string): Promise<BadgeScanResult> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CHECKIN_BADGE_CHECK_IN,
      body: { token },
      parserSchema: BadgeScanResponseSchema,
    })
  }

  async reEnterWithBadge(token: string): Promise<BadgeScanResult> {
    return this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CHECKIN_BADGE_RE_ENTER,
      body: { token },
      parserSchema: BadgeScanResponseSchema,
    })
  }
}
