import { createContext, useContext, useMemo, type ReactNode } from 'react'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import { permissionsFor, type Permissions } from '../utils/permissions'

interface CurrentUserContextValue {
  user: StaffUser | undefined
  permissions: Permissions
}

const CurrentUserContext = createContext<CurrentUserContextValue>({ user: undefined, permissions: permissionsFor(undefined) })

// The signed-in user, loaded once by AdminLayout/StaffLayout for the top bar
// and shared with the pages inside them, so a page (and every one of its
// polls) doesn't fetch /auth/me again. The layouts render their pages only
// once it has loaded (design D-W3).
export function CurrentUserProvider({ user, children }: { user: StaffUser | undefined; children: ReactNode }) {
  const value = useMemo(() => ({ user, permissions: permissionsFor(user) }), [user])
  return <CurrentUserContext.Provider value={value}>{children}</CurrentUserContext.Provider>
}

// `undefined` until the layout's /auth/me request has resolved.
export function useCurrentUser(): StaffUser | undefined {
  return useContext(CurrentUserContext).user
}

// `can(code, branchId?)` for hiding what the user isn't permitted to do
// (design D-W1). Empty until the user has loaded.
export function usePermissions(): Permissions {
  return useContext(CurrentUserContext).permissions
}
