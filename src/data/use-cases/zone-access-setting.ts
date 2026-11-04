import type { TenantSettingsRepository } from '../repositories/tenant-settings-repository'

export class GetZoneAccessEnabledUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(): Promise<boolean> {
    return this.repository.getZoneAccessEnabled()
  }
}

export class SetZoneAccessEnabledUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(enabled: boolean): Promise<void> {
    return this.repository.setZoneAccessEnabled(enabled)
  }
}
