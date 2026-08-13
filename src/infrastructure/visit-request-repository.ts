import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitRequestRepository } from '../data/repositories/visit-request-repository'
import { UploadResponseSchema, type UploadResponse } from '../domain/entities/upload-response-schema'
import { VisitRequestResponseSchema, type VisitRequest, type VisitRequestResponse } from '../domain/entities/visit-request-schema'

export class HttpVisitRequestRepository implements VisitRequestRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async submit(request: VisitRequest): Promise<VisitRequestResponse> {
    return this.apiClient.makeRequest<VisitRequestResponse>({
      endpointConfig: API_ENDPOINTS.CREATE_VISIT_REQUEST,
      body: request,
      parserSchema: VisitRequestResponseSchema,
    })
  }

  async uploadDocument(file: File): Promise<UploadResponse> {
    return this.apiClient.uploadFile<UploadResponse>({
      endpointConfig: API_ENDPOINTS.UPLOAD_VISITOR_DOCUMENT,
      file,
      parserSchema: UploadResponseSchema,
    })
  }
}
