import type { NotificationRepository } from '../repositories/notification-repository'
import type { NotificationFeedItem } from '../../domain/entities/notification-feed-schema'

export class MarkNotificationReadUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(notificationId: string): Promise<NotificationFeedItem> {
    return this.notificationRepository.markRead(notificationId)
  }
}
