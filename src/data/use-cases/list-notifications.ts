import type { ListNotificationsParams, NotificationRepository } from '../repositories/notification-repository'
import type { NotificationFeedPage } from '../../domain/entities/notification-feed-schema'

export class ListNotificationsUseCase {
  private readonly notificationRepository: NotificationRepository

  constructor(notificationRepository: NotificationRepository) {
    this.notificationRepository = notificationRepository
  }

  async execute(params?: ListNotificationsParams): Promise<NotificationFeedPage> {
    return this.notificationRepository.listNotifications(params)
  }
}
