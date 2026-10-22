import { useEffect, useRef, type ReactNode } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useCurrentUser, usePermissions } from '../../context/current-user-context'
import { landingPathFor } from '../../utils/landing-path'
import { signInPathFor } from '../../utils/return-path'
import { useToast } from '../toast/toast-context'

export const NOT_PERMITTED_MESSAGE = "You don't have permission to open that page."

// To sign-in, remembering this page as the return path (`?from=`).
export function SignInRedirect({ loginPath }: { loginPath: string }) {
  const location = useLocation()
  return <Navigate to={signInPathFor(loginPath, location)} replace />
}

// Sends a signed-in user who can't use this page to their own landing page,
// with a "not permitted" message (app-shell "Admin and Staff Areas and Their
// Actions Are Gated by the Caller's Permissions").
export function NotPermittedRedirect({ to }: { to: string }) {
  const navigate = useNavigate()
  const toast = useToast()
  const doneRef = useRef(false)

  useEffect(() => {
    if (doneRef.current) return
    doneRef.current = true
    toast.error(NOT_PERMITTED_MESSAGE)
    navigate(to, { replace: true })
  }, [navigate, toast, to])

  return null
}

// A route's `requires` permission, checked once the layout has the user.
// Renders nothing while redirecting, so no page content flashes.
export function RequirePermission({ requires, children }: { requires?: string; children: ReactNode }) {
  const user = useCurrentUser()
  const { can } = usePermissions()
  if (!requires || can(requires)) return <>{children}</>
  return user ? <NotPermittedRedirect to={landingPathFor(user)} /> : null
}
