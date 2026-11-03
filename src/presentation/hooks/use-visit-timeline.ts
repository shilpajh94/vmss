import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { VisitTimelineEvent, VisitTimelineQuery } from '../../domain/entities/visit-timeline-schema'

const PAGE_SIZE = 20

export type TimelineSortOrder = 'asc' | 'desc'

/** Loads a visit's audit-backed timeline, newest first by default, one page at
 * a time. `enabled` is false for users without `timeline:view`, so no request
 * is made. Sort order and date range changes restart from page 1; "load more"
 * appends the next page. */
export function useVisitTimeline(invitationId: string | undefined, enabled: boolean) {
  const { getVisitTimelineUseCase } = useAppDependencies()
  const [events, setEvents] = useState<VisitTimelineEvent[]>([])
  const [page, setPage] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<TimelineSortOrder>('desc')
  const [occurredAfter, setOccurredAfter] = useState('')
  const [occurredBefore, setOccurredBefore] = useState('')
  // Drops the result of a request that a newer one has superseded.
  const requestId = useRef(0)

  const load = useCallback(
    async (targetPage: number) => {
      if (!invitationId) return
      const id = ++requestId.current
      setIsLoading(true)
      setError(null)
      const query: VisitTimelineQuery = {
        page: targetPage,
        pageSize: PAGE_SIZE,
        sortOrder,
        occurredAfter: occurredAfter ? new Date(occurredAfter).toISOString() : undefined,
        occurredBefore: occurredBefore ? new Date(occurredBefore).toISOString() : undefined,
      }
      try {
        const response = await getVisitTimelineUseCase.execute(invitationId, query)
        if (id !== requestId.current) return
        setEvents((previous) => (targetPage === 1 ? response.data : [...previous, ...response.data]))
        setPage(response.pagination.page)
        setTotalPages(response.pagination.totalPages)
      } catch (caught) {
        if (id !== requestId.current) return
        setError(caught instanceof Error ? caught.message : "We couldn't load the timeline.")
      } finally {
        if (id === requestId.current) setIsLoading(false)
      }
    },
    [getVisitTimelineUseCase, invitationId, sortOrder, occurredAfter, occurredBefore],
  )

  useEffect(() => {
    if (!enabled) return
    setEvents([])
    setPage(0)
    setTotalPages(0)
    void load(1)
    return () => {
      requestId.current++
    }
  }, [enabled, load])

  const loadMore = useCallback(() => load(page + 1), [load, page])
  // Re-requests whichever page failed: the first, or the one after the last loaded.
  const retry = useCallback(() => load(page + 1), [load, page])

  return {
    events,
    isLoading,
    error,
    hasMore: page > 0 && page < totalPages,
    loadMore,
    retry,
    sortOrder,
    setSortOrder,
    occurredAfter,
    setOccurredAfter,
    occurredBefore,
    setOccurredBefore,
  }
}
