import type { CalendarFeedQuery, CalendarRepository } from '../repositories/calendar-repository'
import type { CalendarFeed } from '../../domain/entities/calendar-feed-schema'

export class GetCalendarFeedUseCase {
  private readonly calendarRepository: CalendarRepository

  constructor(calendarRepository: CalendarRepository) {
    this.calendarRepository = calendarRepository
  }

  async execute(query: CalendarFeedQuery): Promise<CalendarFeed> {
    return this.calendarRepository.getFeed(query)
  }
}
