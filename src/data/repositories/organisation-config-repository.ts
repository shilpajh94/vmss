import type { OrganisationConfig } from '../../domain/entities/organisation-config-schema'

export interface OrganisationConfigRepository {
  get(): Promise<OrganisationConfig>
  update(config: OrganisationConfig): Promise<OrganisationConfig>
}
