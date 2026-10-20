import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import type { CalendarEvent } from '../../../../domain/entities/calendar-feed-schema'

// The API's pageSize ceiling: a refresh re-requests the loaded window in
// calls of at most this many.
const MAX_PAGE_SIZE = 100

export type DayPagesStatus = 'idle' | 'loading' | 'error' | 'done'

interface UseDayPagesOptions {
  date: string
  branchId: string | undefined
  statuses: readonly string[] | undefined
  pageSize: number
  // The feed's first `pageSize` events for this date and the day's exact
  // total. A new seed for the same day (a feed refresh) refreshes what's
  // loaded without collapsing it (improve-calendar-scale-and-theme-switch
  // design.md W3).
  seedEvents: CalendarEvent[]
  seedTotal: number
}

function dedupe(events: CalendarEvent[]): CalendarEvent[] {
  const seen = new Set<string>()
  return events.filter((event) => (seen.has(event.id) ? false : (seen.add(event.id), true)))
}

// One day's visits, page by page: starts from the feed's first page, then
// `loadMore()` fetches the next page of that day from the paged day
// endpoint. Rows are de-duplicated by id (a visit added earlier in the
// order between two loads can shift one row).
export function useDayPages({ date, branchId, statuses, pageSize, seedEvents, seedTotal }: UseDayPagesOptions) {
  const { getCalendarDayPageUseCase } = useAppDependencies()
  const [events, setEvents] = useState<CalendarEvent[]>(seedEvents)
  const [total, setTotal] = useState(seedTotal)
  const [status, setStatus] = useState<DayPagesStatus>(seedEvents.length >= seedTotal ? 'done' : 'idle')

  const statusKey = statuses?.join(',') ?? ''
  const key = `${date}|${branchId ?? ''}|${statusKey}`
  // Responses for a superseded day/branch/filter are dropped.
  const generationRef = useRef(0)
  const keyRef = useRef(key)
  const eventsRef = useRef(events)
  eventsRef.current = events
  const inFlightRef = useRef(false)

  const fetchPage = useCallback(
    (page: number, size: number) =>
      getCalendarDayPageUseCase.execute({ date, page, pageSize: size, branchId, statuses }),
    // `statuses` is tracked through `statusKey`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [getCalendarDayPageUseCase, date, branchId, statusKey],
  )

  // A new seed: either a different day/branch/filter (start over from it),
  // or a refresh of the same one (keep everything that's loaded).
  useEffect(() => {
    if (keyRef.current !== key) {
      keyRef.current = key
      generationRef.current += 1
      inFlightRef.current = false
      setEvents(seedEvents)
      setTotal(seedTotal)
      setStatus(seedEvents.length >= seedTotal ? 'done' : 'idle')
      return
    }

    const loaded = eventsRef.current.length
    if (loaded <= seedEvents.length) {
      setEvents(seedEvents)
      setTotal(seedTotal)
      setStatus((previous) => (previous === 'loading' ? previous : seedEvents.length >= seedTotal ? 'done' : 'idle'))
      return
    }

    // More than the first page is loaded: re-request that whole window so
    // statuses and order stay current, without shrinking the list.
    const generation = generationRef.current
    const chunks = Math.ceil(loaded / MAX_PAGE_SIZE)
    Promise.all(Array.from({ length: chunks }, (_, index) => fetchPage(index + 1, MAX_PAGE_SIZE)))
      .then((pages) => {
        if (generation !== generationRef.current) return
        const refreshed = dedupe(pages.flatMap((page) => page.events)).slice(0, loaded)
        const latestTotal = pages[0]?.total ?? seedTotal
        setEvents(refreshed)
        setTotal(latestTotal)
        setStatus((previous) => (previous === 'loading' ? previous : refreshed.length >= latestTotal ? 'done' : 'idle'))
      })
      .catch(() => {
        // Keep the visits on screen; the next refresh tries again.
      })
    // Runs per new seed; the rest is read through refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedEvents, seedTotal, key])

  const loadMore = useCallback(async () => {
    if (inFlightRef.current) return
    const loaded = eventsRef.current.length
    if (loaded >= total) {
      setStatus('done')
      return
    }
    inFlightRef.current = true
    setStatus('loading')
    const generation = generationRef.current
    try {
      const page = await fetchPage(Math.floor(loaded / pageSize) + 1, pageSize)
      if (generation !== generationRef.current) return
      const next = dedupe([...eventsRef.current, ...page.events])
      setEvents(next)
      setTotal(page.total)
      setStatus(next.length >= page.total || page.events.length === 0 ? 'done' : 'idle')
    } catch {
      if (generation === generationRef.current) setStatus('error')
    } finally {
      if (generation === generationRef.current) inFlightRef.current = false
    }
  }, [fetchPage, pageSize, total])

  return { events, total, status, loadMore }
}
