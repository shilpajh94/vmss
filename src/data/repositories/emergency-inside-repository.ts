import type { EmergencyInside } from '../../domain/entities/emergency-inside-schema'

export interface EmergencyInsideRepository {
  /** The full, unpaginated emergency list, grouped by zone. */
  get(branchId?: string): Promise<EmergencyInside>
}
