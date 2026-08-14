import type { StaffAuthRepository } from '../repositories/staff-auth-repository'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

export class GetCurrentStaffUserUseCase {
  private readonly staffAuthRepository: StaffAuthRepository

  constructor(staffAuthRepository: StaffAuthRepository) {
    this.staffAuthRepository = staffAuthRepository
  }

  async execute(): Promise<StaffUser> {
    return this.staffAuthRepository.getCurrentUser()
  }
}
