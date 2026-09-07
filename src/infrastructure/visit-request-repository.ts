import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitRequestRepository, InvitationSubmissionFiles } from '../data/repositories/visit-request-repository'
import { InvitationEnvelopeSchema, type VisitRequest, type VisitRequestResponse } from '../domain/entities/visit-request-schema'

export class HttpVisitRequestRepository implements VisitRequestRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async submit(request: VisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse> {
    const formData = new FormData()
    formData.append('payload', JSON.stringify(request))
    formData.append('primary_contact_id_proof_file', files.primaryContactIdProofFile)
    formData.append('primary_contact_photo_file', files.primaryContactPhotoFile)
    for (const file of files.visitorIdProofFiles) {
      formData.append('visitor_id_proof_files', file)
    }
    if (files.primaryContactPhotoFile) {
      formData.append('primary_contact_photo_file', files.primaryContactPhotoFile)
    }

    const envelope = await this.apiClient.makeMultipartRequest({
      endpointConfig: API_ENDPOINTS.CREATE_VISIT_REQUEST,
      formData,
      parserSchema: InvitationEnvelopeSchema,
    })

    return {
      trackingId: envelope.data.trackingId,
      status: envelope.data.status,
      submittedAt: envelope.data.submittedAt ?? envelope.data.expiresAt,
    }
  }
}
