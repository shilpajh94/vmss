import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'
import { useAppDependencies } from './app-dependencies-context'
import type { NotificationFeedItem } from '../../domain/entities/notification-feed-schema'

// Mirrors the `reason` field the API's push payload carries, and therefore
// each stored notification's `data.reason` (role-based-invitation-workflow):
// `role_assigned` when the recipient was reached via role-at-branch fan-out,
// `delegated` when reached as one specific named person (a step delegate, or
// a newly assigned host). `lifecycle_update` is a point-of-contact role's
// push about a lifecycle change — deliberately unlabelled, since nothing new
// was assigned.
export type NotificationAddressingReason = 'role_assigned' | 'delegated' | 'lifecycle_update'

interface NotificationCenterContextValue {
  notifications: NotificationFeedItem[]
  unreadCount: number
  refresh: () => Promise<void>
  markRead: (notificationId: string) => void
  markAllRead: () => void
  // Subscribes to "new invitation activity arrived" — fired once per feed
  // load that brings in items carrying an `invitationId`, so a dashboard can
  // re-fetch at once instead of waiting for its next poll
  // (live-data-refresh "Dashboards refresh when invitation activity is
  // notified"). Returns the unsubscribe function.
  onInvitationActivity: (callback: () => void) => () => void
  // Bumped once per feed load that brings in any item not seen this
  // session (never by the first load after sign-in); the bell rings on each
  // bump (app-shell "The notification bell rings when a new notification
  // arrives").
  newArrivalCount: number
  // Asks the bell to open its panel (e.g. from a grouped push summary
  // toast). A counter, not a flag, so every request re-triggers and the bell
  // keeps sole ownership of closing.
  openPanel: () => void
  panelOpenRequest: number
}

const NotificationCenterContext = createContext<NotificationCenterContextValue | null>(null)

// The bell shows the most recent page; older items stay retrievable through
// the API's pagination.
const FEED_PAGE_SIZE = 20
const POLL_INTERVAL_MS = 60 * 1000

function isSignedIn(): boolean {
  return Boolean(sessionStorage.getItem('token'))
}

// Server-backed (fix-web-push-and-add-notification-feed): the API persists
// every staff notification, so the bell shows them whether or not this
// browser has push enabled, and survives a reload. A foreground push is only
// a hint to refetch.
export function NotificationCenterProvider({ children }: { children: ReactNode }) {
  const { listNotificationsUseCase, getUnreadNotificationCountUseCase, markNotificationReadUseCase, markAllNotificationsReadUseCase } =
    useAppDependencies()
  const location = useLocation()
  const [notifications, setNotifications] = useState<NotificationFeedItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [newArrivalCount, setNewArrivalCount] = useState(0)
  const [panelOpenRequest, setPanelOpenRequest] = useState(0)
  const wasSignedInRef = useRef(false)
  // Ids already seen this session; undefined until the first load, which
  // only primes the set (old items aren't "new activity").
  const seenIdsRef = useRef<Set<string> | undefined>(undefined)
  const activityListenersRef = useRef(new Set<() => void>())
  // Bumped when a mark-read/mark-all-read starts and again when it settles.
  // A feed response requested under an older version can predate that read
  // on the server, so it's dropped instead of overwriting the optimistic
  // update with a stale unread count.
  const readVersionRef = useRef(0)

  const trackRead = useCallback(<T,>(request: Promise<T>): Promise<T> => {
    readVersionRef.current += 1
    return request.then(
      (result) => {
        readVersionRef.current += 1
        return result
      },
      (error: unknown) => {
        readVersionRef.current += 1
        throw error
      },
    )
  }, [])

  const onInvitationActivity = useCallback((callback: () => void) => {
    activityListenersRef.current.add(callback)
    return () => {
      activityListenersRef.current.delete(callback)
    }
  }, [])

  const refresh = useCallback(() => {
    if (!isSignedIn()) return Promise.resolve()

    const readVersion = readVersionRef.current
    return Promise.all([listNotificationsUseCase.execute({ pageSize: FEED_PAGE_SIZE }), getUnreadNotificationCountUseCase.execute()])
      .then(([page, count]) => {
        if (readVersion !== readVersionRef.current) return
        const seenIds = seenIdsRef.current
        const unseenItems = seenIds === undefined ? [] : page.items.filter((item) => !seenIds.has(item.id))
        const hasNewInvitationActivity = unseenItems.some((item) => Boolean(item.data.invitationId))
        seenIdsRef.current = new Set([...(seenIds ?? []), ...page.items.map((item) => item.id)])

        setNotifications(page.items)
        setUnreadCount(count)
        if (unseenItems.length > 0) setNewArrivalCount((previous) => previous + 1)
        if (hasNewInvitationActivity) activityListenersRef.current.forEach((listener) => listener())
      })
      .catch((error: unknown) => {
        console.error('Failed to load notifications', error)
      })
  }, [listNotificationsUseCase, getUnreadNotificationCountUseCase])

  // Sign-in and sign-out both navigate, and neither emits an event of its
  // own — so the route change is where a fresh session is noticed (load) and
  // an ended one is cleared.
  useEffect(() => {
    const signedIn = isSignedIn()
    if (signedIn && !wasSignedInRef.current) refresh()
    if (!signedIn && wasSignedInRef.current) {
      setNotifications([])
      setUnreadCount(0)
      seenIdsRef.current = undefined
    }
    wasSignedInRef.current = signedIn
  }, [location.pathname, refresh])

  // Polls only while the tab is visible, and catches up as soon as it
  // becomes visible again.
  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }

    const intervalId = window.setInterval(refreshIfVisible, POLL_INTERVAL_MS)
    document.addEventListener('visibilitychange', refreshIfVisible)

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', refreshIfVisible)
    }
  }, [refresh])

  // Optimistic, reverted by a refetch on failure.
  const markRead = useCallback(
    (notificationId: string) => {
      const target = notifications.find((item) => item.id === notificationId)
      if (!target || target.readAt) return

      const readAt = new Date().toISOString()
      setNotifications((previous) => previous.map((item) => (item.id === notificationId ? { ...item, readAt } : item)))
      setUnreadCount((previous) => Math.max(0, previous - 1))

      trackRead(markNotificationReadUseCase.execute(notificationId)).catch((error: unknown) => {
        console.error('Failed to mark notification read', error)
        refresh()
      })
    },
    [notifications, markNotificationReadUseCase, refresh, trackRead],
  )

  const markAllRead = useCallback(() => {
    const readAt = new Date().toISOString()
    setNotifications((previous) => previous.map((item) => (item.readAt ? item : { ...item, readAt })))
    setUnreadCount(0)

    trackRead(markAllNotificationsReadUseCase.execute()).catch((error: unknown) => {
      console.error('Failed to mark all notifications read', error)
      refresh()
    })
  }, [markAllNotificationsReadUseCase, refresh, trackRead])

  const openPanel = useCallback(() => setPanelOpenRequest((previous) => previous + 1), [])

  const value = useMemo(
    () => ({ notifications, unreadCount, refresh, markRead, markAllRead, onInvitationActivity, newArrivalCount, openPanel, panelOpenRequest }),
    [notifications, unreadCount, refresh, markRead, markAllRead, onInvitationActivity, newArrivalCount, openPanel, panelOpenRequest],
  )

  return <NotificationCenterContext.Provider value={value}>{children}</NotificationCenterContext.Provider>
}

export function useNotificationCenter(): NotificationCenterContextValue {
  const context = useContext(NotificationCenterContext)

  if (!context) {
    throw new Error('useNotificationCenter must be used within a NotificationCenterProvider')
  }

  return context
}
