import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { NotificationRepository } from '../data/repositories/notification-repository'
import { DeviceResponseSchema, UnregisterDeviceResponseSchema, type Device } from '../domain/entities/device-schema'

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
}
