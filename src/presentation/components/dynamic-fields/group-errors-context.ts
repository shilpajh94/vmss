import { createContext, useContext } from 'react'

/** The active wizard step's validation errors, so `FieldGroupsSection` can
 * show a group's min-instances error without every step component having to
 * thread an `errors` prop down. */
export const GroupErrorsContext = createContext<Record<string, string>>({})

export const useGroupErrors = () => useContext(GroupErrorsContext)
