import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitRequestSummaryRepository } from '../data/repositories/visit-request-summary-repository'
import {
  VisitRequestSummaryListResponseSchema,
  InvitationActionResultSchema,
  type VisitRequestSummary,
  type VisitRequestSummaryListResponse,
  type InvitationActionResult,
} from '../domain/entities/visit-request-summary-schema'
import {
  InvitationDetailResponseSchema,
  type InvitationDetail,
  type InvitationDetailResponse,
} from '../domain/entities/invitation-detail-schema'

export class HttpVisitRequestSummaryRepository implements VisitRequestSummaryRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(): Promise<VisitRequestSummary[]> {
    const response = await this.apiClient.makeRequest<VisitRequestSummaryListResponse>({
      endpointConfig: API_ENDPOINTS.LIST_VISIT_REQUESTS,
      parserSchema: VisitRequestSummaryListResponseSchema,
    })

    return response.data
  }

  async approve(id: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.APPROVE_INVITATION,
      pathParams: { id },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async reschedule(id: string, preferredVisitDate: string, preferredVisitTime: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.RESCHEDULE_INVITATION,
      pathParams: { id },
      body: { preferredVisitDate, preferredVisitTime },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async deny(id: string, reason: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.DENY_INVITATION,
      pathParams: { id },
      body: { reason },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async approveStep(invitationId: string, stepId: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.APPROVE_INVITATION_STEP,
      pathParams: { invitationId, stepId },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async rejectStep(invitationId: string, stepId: string, reason: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.REJECT_INVITATION_STEP,
      pathParams: { invitationId, stepId },
      body: { reason },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async delegateStep(invitationId: string, stepId: string, delegateUserId: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.DELEGATE_INVITATION_STEP,
      pathParams: { invitationId, stepId },
      body: { delegateUserId },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async getDetail(id: string): Promise<InvitationDetail> {
    const response = await this.apiClient.makeRequest<InvitationDetailResponse>({
      endpointConfig: API_ENDPOINTS.GET_INVITATION_DETAIL,
      pathParams: { id },
      parserSchema: InvitationDetailResponseSchema,
    })

    return response.data
  }
}
