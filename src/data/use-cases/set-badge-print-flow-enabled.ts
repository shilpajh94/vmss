import type { TenantSettingsRepository } from '../repositories/tenant-settings-repository'

export class SetBadgePrintFlowEnabledUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(enabled: boolean): Promise<void> {
    return this.repository.setBadgePrintFlowEnabled(enabled)
  }
}
