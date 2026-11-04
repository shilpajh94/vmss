import type { StaffUser } from '../../domain/entities/staff-user-schema'

// What the signed-in user may do, from `/auth/me`'s per-branch
// `permissionCodes` (design D-W1), so a tenant-defined role gets exactly the
// UI its grants allow, whatever it is called.
export interface Permissions {
  // Every code the user holds at any branch.
  codes: ReadonlySet<string>
  // With `branchId`, only grants at that branch or company-wide count.
  can: (code: string, branchId?: string | null) => boolean
  canAny: (codes: readonly string[]) => boolean
}

// The admin area opens for anyone who manages something in it.
export const ADMIN_AREA_PERMISSIONS = [
  'companies:manage',
  'branches:manage',
  'buildings:manage',
  'floors:manage',
  'departments:manage',
  'desks:manage',
  'gates:manage',
  'employees:manage',
  'users:manage',
  'roles:manage',
  'visitor-categories:manage',
  'approval-workflow-rules:manage',
  'form-builder:manage',
  'kiosks:manage',
  'devices:manage',
  'settings:manage',
  'sso-config:manage',
  'zones:manage',
] as const

// Fallback for an API that doesn't send `permissionCodes` yet: the standard
// roles' grants, copied from the API's `auth/rbac_catalog.py`. A custom role
// gets nothing here. Remove with task 8.7 once every environment runs the
// API that sends the codes.
const ALL = '*'
const FALLBACK_ROLE_PERMISSIONS: Record<string, readonly string[]> = {
  admin: [ALL],
  reception: [
    'branches:view',
    'buildings:view',
    'departments:view',
    'employees:view',
    'desks:view',
    'visitor-categories:view',
    'approval-workflow-rules:view',
    'invitations:create',
    'invitations:view',
    'invitations:view-all',
    'invitations:approve',
    'invitations:deny',
    'invitations:revert-approval',
    'invitations:checkout',
    'invitations:reschedule',
    'invitations:extend',
    'invitations:edit',
    'invitations:badge',
    'invitations:export',
    'visitors:print_badge',
    'timeline:view',
    'documents:view',
    'roles:view',
    'zones:view',
    'emergency:view',
  ],
  security: [
    'branches:view',
    'buildings:view',
    'departments:view',
    'employees:view',
    'gates:view',
    'invitations:view',
    'invitations:view-all',
    'invitations:checkin',
    'invitations:checkout',
    'invitations:export',
    'timeline:view',
    'documents:view',
    'zones:view',
    'emergency:view',
  ],
  host: [
    'branches:view',
    'buildings:view',
    'departments:view',
    'employees:view',
    'visitor-categories:view',
    'approval-workflow-rules:view',
    'invitations:create',
    'invitations:view',
    'invitations:approve',
    'invitations:deny',
    'invitations:revert-approval',
    'invitations:reschedule',
    'invitations:extend',
    'invitations:edit',
    'roles:view',
  ],
}

let warnedAboutFallback = false

interface Grant {
  branchId: string | null
  codes: readonly string[]
}

function grantsFor(user: StaffUser): Grant[] {
  const hasCodes = user.branchRoles.some((branchRole) => branchRole.permissionCodes !== undefined)
  if (!hasCodes && user.branchRoles.length > 0 && !warnedAboutFallback) {
    warnedAboutFallback = true
    console.warn('/auth/me sent no permissionCodes; deriving permissions from role names (design D-W1 fallback).')
  }
  return user.branchRoles.map((branchRole) => ({
    branchId: branchRole.branchId,
    codes: hasCodes
      ? (branchRole.permissionCodes ?? [])
      : (FALLBACK_ROLE_PERMISSIONS[branchRole.roleName.trim().toLowerCase()] ?? []),
  }))
}

const NO_PERMISSIONS: Permissions = { codes: new Set(), can: () => false, canAny: () => false }

export function permissionsFor(user: StaffUser | undefined): Permissions {
  if (!user) return NO_PERMISSIONS
  const grants = grantsFor(user)
  const grantsCode = (grant: Grant, code: string) => grant.codes.includes(ALL) || grant.codes.includes(code)
  const codes = new Set(grants.flatMap((grant) => grant.codes))

  const can = (code: string, branchId?: string | null) =>
    grants.some((grant) => grantsCode(grant, code) && (!branchId || grant.branchId === null || grant.branchId === branchId))

  return {
    codes,
    can,
    canAny: (wanted) => wanted.some((code) => can(code)),
  }
}
