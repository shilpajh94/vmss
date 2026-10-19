import type { NotificationRepository } from '../repositories/notification-repository'

export class GetUnreadNotificationCountUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(): Promise<number> {
    return this.notificationRepository.getUnreadCount()
  }
}
