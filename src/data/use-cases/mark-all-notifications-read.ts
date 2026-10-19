import type { NotificationRepository } from '../repositories/notification-repository'

export class MarkAllNotificationsReadUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(): Promise<void> {
    return this.notificationRepository.markAllRead()
  }
}
