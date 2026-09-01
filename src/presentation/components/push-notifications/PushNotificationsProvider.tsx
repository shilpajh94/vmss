import { useEffect, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { onMessage } from 'firebase/messaging'
import { getFirebaseMessaging } from '../../../infrastructure/firebase/firebase-app'
import { useToast } from '../toast/toast-context'
import { useNotificationCenter } from '../../context/notification-center-context'

// The real push payload's `data` carries `invitationId` (and `trackingId`/`action`),
// not a recipient-role field, so admin vs. staff is inferred from which area this
// tab is currently in.
function buildInvitationPath(invitationId: string): string {
  const basePath = window.location.pathname.startsWith('/admin') ? '/admin/invitations' : '/staff/dashboard'
  return `${basePath}?invitationId=${encodeURIComponent(invitationId)}`
}

// Mounted once at the app root: registers the background service worker and
// listens for foreground pushes for the lifetime of the app, independent of
// which page is currently rendered.
export function PushNotificationsProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  const navigate = useNavigate()
  const notificationCenter = useNotificationCenter()

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return

    navigator.serviceWorker.register('/firebase-messaging-sw.js').catch((error: unknown) => {
      console.error('Failed to register push notification service worker', error)
    })
  }, [])

  useEffect(() => {
    const messaging = getFirebaseMessaging()
    if (!messaging) return

    return onMessage(messaging, (payload) => {
      const invitationId = payload.data?.invitationId
      const message = payload.notification?.body ?? payload.notification?.title ?? 'You have a new notification.'
      const onClick = invitationId ? () => navigate(buildInvitationPath(invitationId)) : undefined

      toast.info(message, { onClick })
      notificationCenter.addNotification({ message, onClick })
    })
  }, [toast, navigate, notificationCenter])

  return <>{children}</>
}
