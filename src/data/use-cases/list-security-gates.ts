import type { SecurityGateRepository } from '../repositories/security-gate-repository'
import type { SecurityGate } from '../../domain/entities/security-gate-schema'

export class ListSecurityGatesUseCase {
  private readonly securityGateRepository: SecurityGateRepository

  constructor(securityGateRepository: SecurityGateRepository) {
    this.securityGateRepository = securityGateRepository
  }

  async execute(): Promise<SecurityGate[]> {
    return this.securityGateRepository.list()
  }
}
