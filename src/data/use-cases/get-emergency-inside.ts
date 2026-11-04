import type { EmergencyInside } from '../../domain/entities/emergency-inside-schema'
import type { EmergencyInsideRepository } from '../repositories/emergency-inside-repository'

export class GetEmergencyInsideUseCase {
  private readonly emergencyInsideRepository: EmergencyInsideRepository

  constructor(emergencyInsideRepository: EmergencyInsideRepository) {
    this.emergencyInsideRepository = emergencyInsideRepository
  }

  execute(branchId?: string): Promise<EmergencyInside> {
    return this.emergencyInsideRepository.get(branchId)
  }
}
