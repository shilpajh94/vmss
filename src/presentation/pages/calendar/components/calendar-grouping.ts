import { formatHour, hourOf } from '../../../utils/calendar-dates'
import type { CalendarEvent } from '../../../../domain/entities/calendar-feed-schema'

export const ANY_TIME = 'any'

export function eventsByDate(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const byDate = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    const list = byDate.get(event.date)
    if (list) list.push(event)
    else byDate.set(event.date, [event])
  }
  return byDate
}

// `ANY_TIME` or the hour (0-23) a visit is scheduled in.
export function slotOf(event: CalendarEvent): string {
  return event.time ? String(hourOf(event.time)) : ANY_TIME
}

export function slotLabel(slot: string): string {
  return slot === ANY_TIME ? 'Any time' : formatHour(Number(slot))
}

export interface SlotGroup {
  slot: string
  events: CalendarEvent[]
}

export interface DayTimeline {
  slots: SlotGroup[]
  // Index of the slot holding the last loaded visit while more of the day
  // is still to load: the loading row and its sentinel go right after that
  // slot's visits. -1 when nothing is loaded yet (the row goes first); null
  // once the day is complete.
  frontier: number | null
}

const HOURS_IN_DAY = 24
// The working day the timeline always shows: 9:00 AM to the 6:00 PM
// heading, inclusive (calendar-working-hours-and-roomier-week design.md D1).
export const WORK_START = 9
export const WORK_END = 18

// The working day, 9:00 AM to 6:00 PM, as hour slots holding the loaded
// visits, plus any hour outside it that has a loaded visit, in hour order,
// then "Any time" once any of those have loaded. The API's standard order is
// by time with any-time visits last, so later working hours than the last
// loaded visit may still gain visits: they are not "empty" until `complete`
// (staff-calendar "Working-hours timeline").
export function buildDayTimeline(events: CalendarEvent[], complete: boolean): DayTimeline {
  const hours: SlotGroup[] = Array.from({ length: HOURS_IN_DAY }, (_, hour) => ({ slot: String(hour), events: [] }))
  const anyTime: SlotGroup = { slot: ANY_TIME, events: [] }
  for (const event of events) {
    const slot = slotOf(event)
    if (slot === ANY_TIME) anyTime.events.push(event)
    else hours[Number(slot)].events.push(event)
  }
  const slots = hours.filter((group, hour) => (hour >= WORK_START && hour <= WORK_END) || group.events.length > 0)
  if (anyTime.events.length > 0) slots.push(anyTime)

  // The last loaded visit's slot always survives the filter: it has a visit.
  const last = events.at(-1)
  const frontier = complete ? null : last ? slots.findIndex((group) => group.slot === slotOf(last)) : -1
  return { slots, frontier }
}
