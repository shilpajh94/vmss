import type { OrganisationConfig } from '../../domain/entities/organisation-config-schema'
import type { UploadResponse } from '../../domain/entities/upload-response-schema'

export interface OrganisationConfigRepository {
  get(): Promise<OrganisationConfig>
  update(config: OrganisationConfig): Promise<OrganisationConfig>
  uploadLogo(file: File): Promise<UploadResponse>
}
