import type { VisitRequestRepository } from '../repositories/visit-request-repository'
import type { UploadResponse } from '../../domain/entities/upload-response-schema'

export class UploadVisitorDocumentUseCase {
  private readonly visitRequestRepository: VisitRequestRepository

  constructor(visitRequestRepository: VisitRequestRepository) {
    this.visitRequestRepository = visitRequestRepository
  }

  async execute(file: File): Promise<UploadResponse> {
    return this.visitRequestRepository.uploadDocument(file)
  }
}
