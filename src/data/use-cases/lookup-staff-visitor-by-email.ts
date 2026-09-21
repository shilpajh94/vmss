import type { StaffVisitorLookupRepository } from '../repositories/staff-visitor-lookup-repository'
import type { StaffVisitorLookup } from '../../domain/entities/staff-visitor-lookup-schema'

export class LookupStaffVisitorByEmailUseCase {
  private readonly staffVisitorLookupRepository: StaffVisitorLookupRepository

  constructor(staffVisitorLookupRepository: StaffVisitorLookupRepository) {
    this.staffVisitorLookupRepository = staffVisitorLookupRepository
  }

  async execute(email: string): Promise<StaffVisitorLookup | null> {
    return this.staffVisitorLookupRepository.lookupByEmail(email)
  }
}
