import type { Device } from "../../domain/entities/device-schema"

export interface NotificationRepository {
  registerDevice(fcmToken: string): Promise<Device>
  unregisterDevice(fcmToken: string): Promise<void>
}
