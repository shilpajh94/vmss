import type { StaffUser } from '../../../domain/entities/staff-user-schema'

// /auth/me doesn't expose permission codes yet, so `devices:manage` is
// approximated by the Admin role (which the backend migration grants it).
// Approve/Enable/Disable visibility already follows the per-row server flags
// (`canApprove` / `canEnable` / `canDisable`); the backend still enforces the
// real permission, so a 403 surfaces as an ApiError. Swap this one check for
// the permission code once the client can read it.
export function canManageDevices(user: StaffUser | undefined): boolean {
  return user?.isAdmin ?? false
}
