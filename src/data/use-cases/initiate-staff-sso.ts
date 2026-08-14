import type { StaffAuthRepository } from '../repositories/staff-auth-repository'
import type { StaffSsoInitiateResponse } from '../../domain/entities/staff-sso-initiate-schema'

export class InitiateStaffSsoUseCase {
  private readonly staffAuthRepository: StaffAuthRepository

  constructor(staffAuthRepository: StaffAuthRepository) {
    this.staffAuthRepository = staffAuthRepository
  }

  async execute(): Promise<StaffSsoInitiateResponse> {
    return this.staffAuthRepository.initiateSso()
  }
}
