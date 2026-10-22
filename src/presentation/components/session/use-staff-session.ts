import { useCallback, useEffect, useState } from 'react'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { StaffUser } from '../../../domain/entities/staff-user-schema'

export type StaffSession =
  | { status: 'signed-out' }
  | { status: 'loading' }
  | { status: 'ready'; user: StaffUser }
  | { status: 'error' }

// The layouts' session check (design D-W3): no token means signed out; with
// one, `/auth/me` decides. A 401 there clears the token and the app-wide
// SessionExpiryListener redirects; any other failure is an error the layout
// shows with a retry, rather than a console line and a page with no user.
export function useStaffSession(): { session: StaffSession; retry: () => void } {
  const { getCurrentStaffUserUseCase } = useAppDependencies()
  const [user, setUser] = useState<StaffUser | undefined>(undefined)
  const [hasFailed, setHasFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const hasToken = Boolean(sessionStorage.getItem('token'))

  useEffect(() => {
    if (!hasToken) return
    let cancelled = false
    setHasFailed(false)
    getCurrentStaffUserUseCase
      .execute()
      .then((loaded) => {
        if (!cancelled) setUser(loaded)
      })
      .catch(() => {
        if (!cancelled) setHasFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [getCurrentStaffUserUseCase, hasToken, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  if (!hasToken) return { session: { status: 'signed-out' }, retry }
  if (user) return { session: { status: 'ready', user }, retry }
  return { session: hasFailed ? { status: 'error' } : { status: 'loading' }, retry }
}
