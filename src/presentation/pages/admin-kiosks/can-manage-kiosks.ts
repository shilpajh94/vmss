import type { StaffUser } from '../../../domain/entities/staff-user-schema'

// /auth/me doesn't expose permission codes yet, so `kiosks:manage` is
// approximated by the Admin role (which holds it). The backend still enforces
// the real permission — a 403 surfaces as an ApiError. Swap this one check for
// the permission code once the client can read it.
export function canManageKiosks(user: StaffUser | undefined): boolean {
  return user?.isAdmin ?? false
}
