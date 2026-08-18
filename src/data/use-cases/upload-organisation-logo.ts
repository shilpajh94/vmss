import type { OrganisationConfigRepository } from '../repositories/organisation-config-repository'
import type { UploadResponse } from '../../domain/entities/upload-response-schema'

export class UploadOrganisationLogoUseCase {
  private readonly organisationConfigRepository: OrganisationConfigRepository

  constructor(organisationConfigRepository: OrganisationConfigRepository) {
    this.organisationConfigRepository = organisationConfigRepository
  }

  async execute(file: File): Promise<UploadResponse> {
    return this.organisationConfigRepository.uploadLogo(file)
  }
}
