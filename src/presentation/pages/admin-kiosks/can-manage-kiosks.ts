import type { StaffUser } from '../../../domain/entities/staff-user-schema'
import { permissionsFor } from '../../utils/permissions'

// The backend still enforces `kiosks:manage`, so a 403 surfaces as an ApiError.
export function canManageKiosks(user: StaffUser | undefined): boolean {
  return permissionsFor(user).can('kiosks:manage')
}
