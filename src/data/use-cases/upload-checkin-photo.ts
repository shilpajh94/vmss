import type { CheckinRepository } from '../repositories/checkin-repository'
import type { CheckinSearchRow } from '../../domain/entities/checkin-schema'

export class UploadCheckinPhotoUseCase {
  private readonly repository: CheckinRepository

  constructor(repository: CheckinRepository) {
    this.repository = repository
  }

  async execute(visitId: string, file: File): Promise<CheckinSearchRow> {
    return this.repository.uploadPhoto(visitId, file)
  }
}
