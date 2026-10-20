import type { CalendarDayPage, CalendarDayPageQuery, CalendarRepository } from '../repositories/calendar-repository'

export class GetCalendarDayPageUseCase {
  private readonly calendarRepository: CalendarRepository

  constructor(calendarRepository: CalendarRepository) {
    this.calendarRepository = calendarRepository
  }

  async execute(query: CalendarDayPageQuery): Promise<CalendarDayPage> {
    return this.calendarRepository.getDayPage(query)
  }
}
