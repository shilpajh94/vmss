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
    // These four are FastAPI `File(...)` parameters on the route
    // (`registrations/router.py::create_walk_in_registration`) — the
    // multipart part name is the parameter name verbatim, snake_case,
    // unlike the bracket-prefixed buckets below (which are parsed
    // generically from `request.form()`, camelCase).
    if (files.primaryContactIdProofFile) formData.append('primary_contact_id_proof_file', files.primaryContactIdProofFile)
    if (files.primaryContactPhotoFile) formData.append('primary_contact_photo_file', files.primaryContactPhotoFile)
    for (const file of files.visitorIdProofFiles) {
      formData.append('visitor_id_proof_files', file)
    }
    for (const file of files.visitorPhotoFiles) {
      formData.append('visitor_photo_files', file)
    }
    for (const [fieldId, groupFiles] of Object.entries(files.groupFieldFiles)) {
      for (const file of groupFiles) {
        formData.append(`groupFieldFiles[${fieldId}]`, file)
      }
    }
    for (const [fieldId, file] of Object.entries(files.primaryContactCustomFieldFiles)) {
      formData.append(`primaryContactCustomFieldFiles[${fieldId}]`, file)
    }
    for (const [fieldId, fieldFiles] of Object.entries(files.visitorCustomFieldFiles)) {
      for (const file of fieldFiles) {
        formData.append(`visitorCustomFieldFiles[${fieldId}]`, file)
      }
    }
    for (const [fieldId, fieldFiles] of Object.entries(files.vehicleCustomFieldFiles)) {
      for (const file of fieldFiles) {
        formData.append(`vehicleCustomFieldFiles[${fieldId}]`, file)
      }
    }
    for (const [fieldId, file] of Object.entries(files.customFieldFiles)) {
      formData.append(`customFieldFiles[${fieldId}]`, file)
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
