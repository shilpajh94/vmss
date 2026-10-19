import type { Device } from "../../domain/entities/device-schema"
import type { NotificationFeedItem, NotificationFeedPage } from "../../domain/entities/notification-feed-schema"

export interface ListNotificationsParams {
  page?: number
  pageSize?: number
  unreadOnly?: boolean
}

export interface NotificationRepository {
  registerDevice(fcmToken: string): Promise<Device>
  unregisterDevice(fcmToken: string): Promise<void>
  listNotifications(params?: ListNotificationsParams): Promise<NotificationFeedPage>
  getUnreadCount(): Promise<number>
  markRead(notificationId: string): Promise<NotificationFeedItem>
  markAllRead(): Promise<void>
}
