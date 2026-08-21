import type { SecurityGateRepository } from '../repositories/security-gate-repository'
import type { SecurityGate, SecurityGateInput } from '../../domain/entities/security-gate-schema'

export class CreateSecurityGateUseCase {
  private readonly securityGateRepository: SecurityGateRepository

  constructor(securityGateRepository: SecurityGateRepository) {
    this.securityGateRepository = securityGateRepository
  }

  async execute(input: SecurityGateInput): Promise<SecurityGate> {
    return this.securityGateRepository.create(input)
  }
}
