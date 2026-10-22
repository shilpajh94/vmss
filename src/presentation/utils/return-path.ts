import type { StaffUser } from '../../domain/entities/staff-user-schema'
import { landingPathFor } from './landing-path'
import { ADMIN_AREA_PERMISSIONS, permissionsFor } from './permissions'

const SIGN_IN_PATHS = ['/admin/login', '/staff/login']

// Where to send a signed-out user so they come back here after signing in
// (staff-login "Successful sign-in lands on a role-based dashboard").
export function signInPathFor(loginPath: string, location: { pathname: string; search: string; hash?: string }): string {
  const from = `${location.pathname}${location.search}${location.hash ?? ''}`
  return `${loginPath}?from=${encodeURIComponent(from)}`
}

// `from` as an in-app path, or undefined when it points anywhere else (another
// origin, a `//host` or `javascript:` value) or back at a sign-in page.
export function safeReturnPath(from: string | null | undefined, origin: string): string | undefined {
  if (!from || !from.startsWith('/')) return undefined
  let url: URL
  try {
    url = new URL(from, origin)
  } catch {
    return undefined
  }
  if (url.origin !== origin || SIGN_IN_PATHS.includes(url.pathname)) return undefined
  return `${url.pathname}${url.search}${url.hash}`
}

// The page to open after sign-in: the requested one when it is in the app
// and in an area this user may use, otherwise their role's landing page.
// A page inside an area can still turn them away (its own permission), and
// then sends them to the landing page with a "not permitted" message.
export function postSignInPath(user: StaffUser, from: string | null | undefined, origin: string): string {
  const path = safeReturnPath(from, origin)
  if (!path) return landingPathFor(user)
  if (path.startsWith('/admin/') && !permissionsFor(user).canAny(ADMIN_AREA_PERMISSIONS)) return landingPathFor(user)
  if (path.startsWith('/reception/') && !user.isReception) return landingPathFor(user)
  return path
}

// SSO leaves the app for the identity provider, so the return path rides
// in sessionStorage across that round trip instead of the URL.
const SSO_RETURN_KEY = 'auth:return-to'

export function rememberSsoReturnPath(from: string | null): void {
  try {
    if (from) sessionStorage.setItem(SSO_RETURN_KEY, from)
    else sessionStorage.removeItem(SSO_RETURN_KEY)
  } catch {
    // Storage blocked: the user just lands on their dashboard.
  }
}

export function takeSsoReturnPath(): string | null {
  try {
    const from = sessionStorage.getItem(SSO_RETURN_KEY)
    sessionStorage.removeItem(SSO_RETURN_KEY)
    return from
  } catch {
    return null
  }
}
