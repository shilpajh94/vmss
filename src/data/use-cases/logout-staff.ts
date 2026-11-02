import type { StaffAuthRepository } from '../repositories/staff-auth-repository'

export class LogoutStaffUseCase {
  private readonly staffAuthRepository: StaffAuthRepository

  constructor(staffAuthRepository: StaffAuthRepository) {
    this.staffAuthRepository = staffAuthRepository
  }

  async execute(): Promise<void> {
    return this.staffAuthRepository.logout()
  }
}
