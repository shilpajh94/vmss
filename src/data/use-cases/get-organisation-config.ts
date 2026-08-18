import type { OrganisationConfigRepository } from '../repositories/organisation-config-repository'
import type { OrganisationConfig } from '../../domain/entities/organisation-config-schema'

export class GetOrganisationConfigUseCase {
  private readonly organisationConfigRepository: OrganisationConfigRepository

  constructor(organisationConfigRepository: OrganisationConfigRepository) {
    this.organisationConfigRepository = organisationConfigRepository
  }

  async execute(): Promise<OrganisationConfig> {
    return this.organisationConfigRepository.get()
  }
}
