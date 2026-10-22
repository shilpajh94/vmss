import { useEffect, useRef, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { whenFirebaseMessagingReady } from '../../../infrastructure/firebase/firebase-app'
import { useToast } from '../toast/toast-context'
import { useNotificationCenter, type NotificationAddressingReason } from '../../context/notification-center-context'
import { usePushNotifications } from '../../hooks/use-push-notifications'
import { useAppDependencies } from '../../context/app-dependencies-context'
import { buildInvitationPath } from '../../utils/notification-links'

// role-based-invitation-workflow: the push payload's `data` carries
// `assignedRoleId`/`assignedUserId`/`reason` so a role-addressed
// notification ("New invitation for Front Office") can be visually
// distinguished from a person-addressed one ("Delegated to you"). Resolving
// `assignedRoleId` to a display name needs the tenant's role list, which
// this provider (mounted once at the app root, independent of which board
// page is open) doesn't otherwise have — fetched once here rather than
// threading the board's own `roleNameById` state down into a
// page-independent provider.
function buildAddressingLabel(reason: NotificationAddressingReason | undefined, roleName: string | undefined): string | undefined {
  if (reason === 'role_assigned') return `New invitation for ${roleName ?? 'your role'}`
  if (reason === 'delegated') return 'Delegated to you'
  return undefined
}

// Firebase can rotate the FCM token at any point during a long-lived session
// with no persistent refresh listener, so a mount-only re-check would still miss
// a rotation that happens while the tab stays open. Re-checking periodically and
// whenever the tab regains focus catches it without needing a full reload.
const RE_REGISTER_INTERVAL_MS = 30 * 60 * 1000

// `visibilitychange` fires far more often than "the user came back after a long
// break" — e.g. a native file-picker dialog (opened from an upload field, such
// as the ID-proof upload during visit-request creation) hides and re-shows the
// tab, firing this event on both transitions. Without a cooldown, one dialog can
// trigger several redundant re-registration calls seconds apart.
const MIN_RE_REGISTER_GAP_MS = 5 * 60 * 1000

// The background worker pulls the Firebase SDK from gstatic, so it is only
// registered for a signed-in session, never on a public page.
let hasRegisteredServiceWorker = false
function registerServiceWorkerOnce(): void {
  if (hasRegisteredServiceWorker || !('serviceWorker' in navigator)) return
  hasRegisteredServiceWorker = true
  navigator.serviceWorker.register('/firebase-messaging-sw.js').catch((error: unknown) => {
    console.error('Failed to register push notification service worker', error)
  })
}

// Mounted once at the app root: registers the background service worker
// (once signed in) and listens for foreground pushes for the lifetime of the
// app, independent of which page is currently rendered.
export function PushNotificationsProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  const navigate = useNavigate()
  const notificationCenter = useNotificationCenter()
  const { refreshRegistrationIfGranted } = usePushNotifications()
  const { listRolesUseCase } = useAppDependencies()
  const lastRegisteredAtRef = useRef(0)
  // Populated once, lazily, the first time a role-addressed push actually
  // needs a name — not on mount, since this provider renders before a
  // caller may be signed in at all.
  const roleNameByIdRef = useRef<Record<string, string> | undefined>(undefined)

  // `notificationCenter`'s context value changes identity every time a notification
  // is added (its `notifications` state updates), and `toast`/`navigate` can also
  // change across renders. Reading them through a ref lets the onMessage
  // subscription below stay mounted once instead of tearing down and
  // re-subscribing on every received message — a resubscribe-per-message pattern
  // that silently stopped delivering anything after the first push.
  const latestRef = useRef({ toast, navigate, notificationCenter, listRolesUseCase })
  useEffect(() => {
    latestRef.current = { toast, navigate, notificationCenter, listRolesUseCase }
  })

  // A signed-in device re-registers on mount, on an interval, and whenever the
  // tab regains focus, so a rotated FCM token gets picked up without waiting for
  // the host to log out and back in. This never prompts for permission — only
  // the bell's "Enable notifications" button does, from a click.
  useEffect(() => {
    const reRegisterIfSignedIn = () => {
      if (document.visibilityState !== 'visible') return
      if (!sessionStorage.getItem('token')) return
      registerServiceWorkerOnce()

      const now = Date.now()
      if (now - lastRegisteredAtRef.current < MIN_RE_REGISTER_GAP_MS) return
      lastRegisteredAtRef.current = now

      void refreshRegistrationIfGranted()
    }

    reRegisterIfSignedIn()

    const intervalId = window.setInterval(reRegisterIfSignedIn, RE_REGISTER_INTERVAL_MS)
    document.addEventListener('visibilitychange', reRegisterIfSignedIn)

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', reRegisterIfSignedIn)
    }
  }, [refreshRegistrationIfGranted])

  // Subscribes once the Firebase SDK has been loaded by a signed-in
  // registration (`refreshRegistrationIfGranted`), so a public page never
  // downloads it just to listen.
  useEffect(() => {
    let cancelled = false
    let unsubscribe: (() => void) | undefined
    void whenFirebaseMessagingReady().then(({ messaging, onMessage }) => {
      if (cancelled) return
      unsubscribe = onMessage(messaging, (payload) => {
        const { toast, navigate, notificationCenter, listRolesUseCase } = latestRef.current
        const invitationId = payload.data?.invitationId
        const message = payload.notification?.body ?? payload.notification?.title ?? 'You have a new notification.'
        const onClick = invitationId ? () => navigate(buildInvitationPath(invitationId)) : undefined
        const reason = payload.data?.reason as NotificationAddressingReason | undefined
        const assignedRoleId = payload.data?.assignedRoleId

        const dispatch = (roleName: string | undefined) => {
          const addressingLabel = buildAddressingLabel(reason, roleName)
          const displayMessage = addressingLabel ? `${addressingLabel}: ${message}` : message
          // A push arriving while another push toast is still up joins it as
          // one "N new notifications" summary that opens the bell, so a burst
          // never floods the screen (notifications "A burst of push
          // notifications is grouped into one summary").
          toast.info(displayMessage, {
            onClick,
            groupKey: 'push',
            groupSummary: (count) => ({ message: `${count} new notifications`, onClick: () => latestRef.current.notificationCenter.openPanel() }),
          })
          // The API recorded this push before sending it, so a refetch finds
          // it — the bell never shows a client-only item the server lacks.
          notificationCenter.refresh()
        }

        if (reason === 'role_assigned' && assignedRoleId && !roleNameByIdRef.current) {
          listRolesUseCase
            .execute()
            .then((roles) => {
              roleNameByIdRef.current = Object.fromEntries(roles.map((role) => [role.id, role.name]))
              dispatch(roleNameByIdRef.current[assignedRoleId])
            })
            .catch((error: unknown) => {
              console.error('Failed to resolve role name for push notification label', error)
              dispatch(undefined)
            })
          return
        }

        dispatch(assignedRoleId ? roleNameByIdRef.current?.[assignedRoleId] : undefined)
      })
    })
    return () => {
      cancelled = true
      unsubscribe?.()
    }
    // Intentionally subscribes once for the component's lifetime — see latestRef above.
  }, [])

  return <>{children}</>
}
