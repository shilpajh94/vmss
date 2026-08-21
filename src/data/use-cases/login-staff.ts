import type { StaffAuthRepository } from '../repositories/staff-auth-repository'
import type { StaffLoginResult } from '../../domain/entities/staff-login-schema'

export class LoginStaffUseCase {
  private readonly staffAuthRepository: StaffAuthRepository

  constructor(staffAuthRepository: StaffAuthRepository) {
    this.staffAuthRepository = staffAuthRepository
  }

  async execute(email: string, password: string): Promise<StaffLoginResult> {
    return this.staffAuthRepository.login(email, password)
  }
}
