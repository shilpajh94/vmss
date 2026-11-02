import type { TenantSettingsRepository } from '../repositories/tenant-settings-repository'

export class GetBadgePrintFlowEnabledUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(): Promise<boolean> {
    return this.repository.getBadgePrintFlowEnabled()
  }
}
