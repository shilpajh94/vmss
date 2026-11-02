import type { StaffUser } from '../../../domain/entities/staff-user-schema'
import { permissionsFor } from '../../utils/permissions'

// Approve/Enable/Disable visibility already follows the per-row server flags
// (`canApprove` / `canEnable` / `canDisable`); this gates the page's own
// management actions. The backend still enforces the permission, so a 403
// surfaces as an ApiError.
export function canManageDevices(user: StaffUser | undefined): boolean {
  return permissionsFor(user).can('devices:manage')
}
