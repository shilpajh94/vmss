import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type {
  EditInvitationFields,
  ListVisitRequestsParams,
  VisitRequestSummaryRepository,
  VisitRequestsPage,
} from '../data/repositories/visit-request-summary-repository'
import {
  VisitRequestSummaryListResponseSchema,
  InvitationActionResultSchema,
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

  async list(params?: ListVisitRequestsParams): Promise<VisitRequestsPage> {
    const response = await this.apiClient.makeRequest<VisitRequestSummaryListResponse>({
      endpointConfig: API_ENDPOINTS.LIST_VISIT_REQUESTS,
      queryParams: {
        relevantToMe: params?.relevantToMe ? true : undefined,
        status: params?.status,
        registrationType: params?.registrationType,
        source: params?.source,
        search: params?.search,
        purposeOfVisit: params?.purposeOfVisit,
        page: params?.page,
        pageSize: params?.pageSize,
      },
      parserSchema: VisitRequestSummaryListResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
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

  async edit(id: string, fields: EditInvitationFields): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.EDIT_INVITATION,
      pathParams: { id },
      // `pocUserId` is a UUID column server-side; the form seeds it to `''`
      // when the invitation has no POC yet, and an empty string fails the
      // backend's UUID parser ("expected length 32... found 0") instead of
      // being treated as "unchanged". Omit it entirely unless one was picked.
      body: { ...fields, pocUserId: fields.pocUserId || undefined },
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

  async revertApproval(id: string, reason: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.REVERT_INVITATION_APPROVAL,
      pathParams: { id },
      body: { reason },
      parserSchema: InvitationActionResultSchema,
    })

    if (!response.success) {
      throw new Error(response.message)
    }
  }

  async checkOut(id: string, idempotencyKey: string): Promise<void> {
    const response = await this.apiClient.makeRequest<InvitationActionResult>({
      endpointConfig: API_ENDPOINTS.CHECK_OUT_INVITATION,
      pathParams: { id },
      headers: { 'Idempotency-Key': idempotencyKey },
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
