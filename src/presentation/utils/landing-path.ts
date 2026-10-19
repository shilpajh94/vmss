import type { StaffUser } from '../../domain/entities/staff-user-schema'

// Where every staff login lands — one rule for the password and SSO paths, so
// they can't drift apart again (SSO used to send reception to the staff board).
export function landingPathFor(user: Pick<StaffUser, 'isAdmin' | 'isReception'>): string {
  if (user.isAdmin) return '/admin/dashboard'
  if (user.isReception) return '/reception/dashboard'
  return '/staff/dashboard'
}
