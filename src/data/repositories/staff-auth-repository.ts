import type { StaffSsoInitiateResponse } from '../../domain/entities/staff-sso-initiate-schema'

export interface StaffAuthRepository {
  initiateSso(): Promise<StaffSsoInitiateResponse>
}
