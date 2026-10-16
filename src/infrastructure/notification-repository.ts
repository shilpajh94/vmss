import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { ListNotificationsParams, NotificationRepository } from '../data/repositories/notification-repository'
import { DeviceResponseSchema, UnregisterDeviceResponseSchema, type Device } from '../domain/entities/device-schema'
import {
  MarkAllNotificationsReadResponseSchema,
  NotificationFeedPageResponseSchema,
  NotificationResponseSchema,
  NotificationUnreadCountResponseSchema,
  type NotificationFeedItem,
  type NotificationFeedPage,
} from '../domain/entities/notification-feed-schema'

export class HttpNotificationRepository implements NotificationRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async registerDevice(fcmToken: string): Promise<Device> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.REGISTER_DEVICE,
      body: { fcmToken, platform: 'web' },
      parserSchema: DeviceResponseSchema,
    })

    return response.data
  }

  async unregisterDevice(fcmToken: string): Promise<void> {
    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UNREGISTER_DEVICE,
      pathParams: { fcmToken },
      parserSchema: UnregisterDeviceResponseSchema,
    })
  }

  async listNotifications({ page = 1, pageSize = 20, unreadOnly = false }: ListNotificationsParams = {}): Promise<NotificationFeedPage> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_NOTIFICATIONS,
      queryParams: { page, pageSize, unreadOnly: unreadOnly || undefined },
      parserSchema: NotificationFeedPageResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async getUnreadCount(): Promise<number> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.NOTIFICATIONS_UNREAD_COUNT,
      parserSchema: NotificationUnreadCountResponseSchema,
    })

    return response.data.unreadCount
  }

  async markRead(notificationId: string): Promise<NotificationFeedItem> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.MARK_NOTIFICATION_READ,
      pathParams: { id: notificationId },
      parserSchema: NotificationResponseSchema,
    })

    return response.data
  }

  async markAllRead(): Promise<void> {
    await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.MARK_ALL_NOTIFICATIONS_READ,
      parserSchema: MarkAllNotificationsReadResponseSchema,
    })
  }
}
