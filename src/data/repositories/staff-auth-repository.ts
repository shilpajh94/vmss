import type { StaffSsoInitiateResponse } from '../../domain/entities/staff-sso-initiate-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

export interface StaffAuthRepository {
  initiateSso(): Promise<StaffSsoInitiateResponse>
  getCurrentUser(): Promise<StaffUser>
}
