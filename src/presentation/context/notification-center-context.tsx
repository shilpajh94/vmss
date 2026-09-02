import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export interface NotificationCenterItem {
  id: string
  message: string
  receivedAt: string
  read: boolean
  onClick?: () => void
}

interface AddNotificationInput {
  message: string
  onClick?: () => void
}

interface NotificationCenterContextValue {
  notifications: NotificationCenterItem[]
  unreadCount: number
  addNotification: (input: AddNotificationInput) => void
  markAllRead: () => void
}

const NotificationCenterContext = createContext<NotificationCenterContextValue | null>(null)

// Client-side only: there's no backend "list my notifications" endpoint, so this
// is just the pushes received during the current session/tab, most recent first.
const MAX_NOTIFICATIONS = 50

export function NotificationCenterProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationCenterItem[]>([])

  const addNotification = useCallback(({ message, onClick }: AddNotificationInput) => {
    const item: NotificationCenterItem = {
      id: crypto.randomUUID(),
      message,
      onClick,
      receivedAt: new Date().toISOString(),
      read: false,
    }
    setNotifications((previous) => [item, ...previous].slice(0, MAX_NOTIFICATIONS))
  }, [])

  const markAllRead = useCallback(() => {
    setNotifications((previous) => previous.map((item) => (item.read ? item : { ...item, read: true })))
  }, [])

  const unreadCount = useMemo(() => notifications.filter((item) => !item.read).length, [notifications])

  const value = useMemo(
    () => ({ notifications, unreadCount, addNotification, markAllRead }),
    [notifications, unreadCount, addNotification, markAllRead],
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
