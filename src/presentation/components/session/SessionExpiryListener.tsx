import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { SESSION_EXPIRED_EVENT } from '../../../data/api/api-client'
import { useToast } from '../toast/toast-context'

// Mounted once at the app root: reacts to ApiClient signaling a dead session
// (via a plain browser event, since `data/` cannot import `presentation/`) from
// any page, without each page's own hook needing to detect it individually.
export function SessionExpiryListener() {
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    const handleSessionExpired = () => {
      toast.error('Your session has expired. Please sign in again.')
      navigate(window.location.pathname.startsWith('/admin') ? '/admin/login' : '/staff/login')
    }

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired)
  }, [navigate, toast])

  return null
}
