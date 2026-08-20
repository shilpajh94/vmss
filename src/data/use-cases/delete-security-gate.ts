import type { SecurityGateRepository } from '../repositories/security-gate-repository'

export class DeleteSecurityGateUseCase {
  private readonly securityGateRepository: SecurityGateRepository

  constructor(securityGateRepository: SecurityGateRepository) {
    this.securityGateRepository = securityGateRepository
  }

  async execute(id: string): Promise<void> {
    return this.securityGateRepository.remove(id)
  }
}
