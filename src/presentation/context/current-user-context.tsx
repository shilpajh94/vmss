import { createContext, useContext, type ReactNode } from 'react'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

const CurrentUserContext = createContext<StaffUser | undefined>(undefined)

// The signed-in user, loaded once by AdminLayout/StaffLayout for the top bar
// and shared with the pages inside them, so a page (and every one of its
// polls) doesn't fetch /auth/me again.
export function CurrentUserProvider({ user, children }: { user: StaffUser | undefined; children: ReactNode }) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>
}

// `undefined` until the layout's /auth/me request has resolved.
export function useCurrentUser(): StaffUser | undefined {
  return useContext(CurrentUserContext)
}
