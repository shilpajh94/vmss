import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { SESSION_EXPIRED_EVENT } from '../../../data/api/api-client'
import { useToast } from '../toast/toast-context'

// PushNotificationsProvider (mounted app-wide, above <Routes>) keeps re-registering
// the device on an interval/focus as long as a token is *present* in sessionStorage,
// without checking it's still valid. If that background call is what surfaces the
// 401 while the user is sitting on a public page (or a login page) with a stale
// leftover token, redirecting them away would be disruptive for a page that never
// required auth — so only react on the protected areas below.
function isProtectedRoute(pathname: string): boolean {
  return (pathname.startsWith('/staff/') && pathname !== '/staff/login') || (pathname.startsWith('/admin/') && pathname !== '/admin/login')
}

// Mounted once at the app root: reacts to ApiClient signaling a dead session
// (via a plain browser event, since `data/` cannot import `presentation/`) from
// any page, without each page's own hook needing to detect it individually.
export function SessionExpiryListener() {
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    const handleSessionExpired = () => {
      if (!isProtectedRoute(window.location.pathname)) return

      toast.error('Your session has expired. Please sign in again.')
      navigate(window.location.pathname.startsWith('/admin') ? '/admin/login' : '/staff/login')
    }

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
  }, [navigate, toast])

  return null
}
