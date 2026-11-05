import type { TenantSettingsRepository } from '../repositories/tenant-settings-repository'

export class GetBadgePrintRequiresIdVerificationUseCase {
  private readonly repository: TenantSettingsRepository

  constructor(repository: TenantSettingsRepository) {
    this.repository = repository
  }

  async execute(): Promise<boolean> {
    return this.repository.getBadgePrintRequiresIdVerification()
  }
}
