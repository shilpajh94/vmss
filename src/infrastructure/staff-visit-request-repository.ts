import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { InvitationSubmissionFiles } from '../data/repositories/visit-request-repository'
import type { StaffVisitRequestRepository } from '../data/repositories/staff-visit-request-repository'
import type { StaffVisitRequest } from '../domain/entities/staff-visit-request-schema'
import { InvitationEnvelopeSchema, type VisitRequestResponse } from '../domain/entities/visit-request-schema'

export class HttpStaffVisitRequestRepository implements StaffVisitRequestRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async submit(request: StaffVisitRequest, files: InvitationSubmissionFiles): Promise<VisitRequestResponse> {
    const formData = new FormData()
    formData.append('payload', JSON.stringify(request))
    // See visit-request-repository.ts's matching comment on why these four
    // are snake_case while the bracket-prefixed buckets below are camelCase.
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
      endpointConfig: API_ENDPOINTS.STAFF_CREATE_VISIT_REQUEST,
      formData,
      parserSchema: InvitationEnvelopeSchema,
    })

    return {
      trackingId: envelope.data.trackingId,
      invitationId: envelope.data.id,
      status: envelope.data.status,
      submittedAt: envelope.data.submittedAt ?? envelope.data.expiresAt,
    }
  }
}
