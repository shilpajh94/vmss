import type { NotificationRepository } from '../repositories/notification-repository'

export class UnregisterDeviceUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(fcmToken: string): Promise<void> {
    return this.notificationRepository.unregisterDevice(fcmToken)
  }
}
