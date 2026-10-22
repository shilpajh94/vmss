import type { StaffLoginResult } from '../../domain/entities/staff-login-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

export interface StaffAuthRepository {
  login(email: string, password: string): Promise<StaffLoginResult>
  getCurrentUser(): Promise<StaffUser>
  // Records the sign-out server-side (the audit trail's logout event).
  logout(): Promise<void>
}
