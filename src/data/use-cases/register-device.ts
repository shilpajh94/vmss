import type { NotificationRepository } from '../repositories/notification-repository'
import type { Device } from '../../domain/entities/device-schema'

export class RegisterDeviceUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(fcmToken: string): Promise<Device> {
    return this.notificationRepository.registerDevice(fcmToken)
  }
}
