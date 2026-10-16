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
  refresh: () => void
  markRead: (notificationId: string) => void
  markAllRead: () => void
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
  const wasSignedInRef = useRef(false)

  const refresh = useCallback(() => {
    if (!isSignedIn()) return

    Promise.all([listNotificationsUseCase.execute({ pageSize: FEED_PAGE_SIZE }), getUnreadNotificationCountUseCase.execute()])
      .then(([page, count]) => {
        setNotifications(page.items)
        setUnreadCount(count)
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

      markNotificationReadUseCase.execute(notificationId).catch((error: unknown) => {
        console.error('Failed to mark notification read', error)
        refresh()
      })
    },
    [notifications, markNotificationReadUseCase, refresh],
  )

  const markAllRead = useCallback(() => {
    const readAt = new Date().toISOString()
    setNotifications((previous) => previous.map((item) => (item.readAt ? item : { ...item, readAt })))
    setUnreadCount(0)

    markAllNotificationsReadUseCase.execute().catch((error: unknown) => {
      console.error('Failed to mark all notifications read', error)
      refresh()
    })
  }, [markAllNotificationsReadUseCase, refresh])

  const value = useMemo(
    () => ({ notifications, unreadCount, refresh, markRead, markAllRead }),
    [notifications, unreadCount, refresh, markRead, markAllRead],
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
