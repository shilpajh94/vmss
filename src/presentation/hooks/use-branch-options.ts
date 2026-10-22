import { useEffect, useMemo, useState } from 'react'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

// Roles that see branch-wide invitations (`invitations:view-all`).
const BRANCH_WIDE_ROLES = new Set(['admin', 'reception', 'security'])

export interface BranchOption {
  id: string
  name: string
}

// Branch ids the user can scope a branch-wide page to: undefined means every
// branch (a company-wide grant), otherwise the explicit set.
function authorizedBranchIds(user: StaffUser): Set<string> | undefined {
  const grants = user.branchRoles.filter((grant) => BRANCH_WIDE_ROLES.has(grant.roleName.toLowerCase()))
  if (grants.some((grant) => grant.branchId === null)) return undefined
  return new Set(grants.map((grant) => grant.branchId).filter((id): id is string => id !== null))
}

// The branches a branch selector offers (the branch dashboards and the
// calendar). Names come from the public branch list, narrowed to the ones the
// user holds a branch-wide role at, and only when there's a choice — an
// empty list means "render no selector". The API stays authoritative: an
// option it doesn't allow is refused with 403 (add-staff-calendar W1).
export function useBranchOptions(currentUser: StaffUser | undefined, enabled: boolean): BranchOption[] {
  const { listBranchesUseCase } = useAppDependencies()
  const [branchOptions, setBranchOptions] = useState<BranchOption[]>([])

  useEffect(() => {
    if (!currentUser || !enabled) return
    const authorized = authorizedBranchIds(currentUser)
    if (authorized !== undefined && authorized.size < 2) {
      setBranchOptions([])
      return
    }
    let isCurrent = true
    listBranchesUseCase
      .execute()
      .then((branches) => {
        if (!isCurrent) return
        setBranchOptions(
          branches
            .filter((branch) => authorized === undefined || authorized.has(branch.id))
            .map((branch) => ({ id: branch.id, name: branch.name })),
        )
      })
      .catch((error: unknown) => {
        // The selector is an enhancement; the page works without it.
        console.error('Failed to load branches for the branch selector', error)
      })
    return () => {
      isCurrent = false
    }
  }, [currentUser, enabled, listBranchesUseCase])

  return useMemo(() => (branchOptions.length > 1 ? branchOptions : []), [branchOptions])
}
