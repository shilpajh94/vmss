import type { StaffVisitorLookup } from '../../domain/entities/staff-visitor-lookup-schema'

export interface StaffVisitorLookupRepository {
  lookupByEmail(email: string): Promise<StaffVisitorLookup | null>
  lookupByPhone(phone: string): Promise<StaffVisitorLookup | null>
}
