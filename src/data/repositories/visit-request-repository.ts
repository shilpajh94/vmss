import type { UploadResponse } from '../../domain/entities/upload-response-schema'
import type { VisitRequest, VisitRequestResponse } from '../../domain/entities/visit-request-schema'

export interface VisitRequestRepository {
  submit(request: VisitRequest): Promise<VisitRequestResponse>
  uploadDocument(file: File): Promise<UploadResponse>
}
