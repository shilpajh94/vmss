import type { TenantSettingsRepository } from '../repositories/tenant-settings-repository'

export class SetBadgePrintRequiresIdVerificationUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(required: boolean): Promise<void> {
    return this.repository.setBadgePrintRequiresIdVerification(required)
  }
}
