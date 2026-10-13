import { useCallback, useEffect, useRef, useState } from 'react'
import type { ListVisitRequestsParams, VisitRequestsPage } from '../../data/repositories/visit-request-summary-repository'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'

export type BoardStatus = 'requested' | 'approved' | 'checked_in' | 'denied'

const BOARD_STATUSES: readonly BoardStatus[] = ['requested', 'approved', 'checked_in', 'denied']

// Board column -> the `status` value `GET /invitations` filters on. A
// workflow invitation stays `submitted` until its last step clears (see
// board-sticky-headers-lazy-load design.md Decision 2), so each column is
// exactly one server-side status query.
const API_STATUS_BY_BOARD_STATUS: Record<BoardStatus, string> = {
  requested: 'submitted',
  approved: 'approved',
  checked_in: 'checked_in',
  denied: 'denied',
}

export function boardStatusForApiStatus(apiStatus: string): BoardStatus | undefined {
  return BOARD_STATUSES.find((status) => API_STATUS_BY_BOARD_STATUS[status] === apiStatus)
}

export const BOARD_PAGE_SIZE = 20
const API_MAX_PAGE_SIZE = 100

export interface BoardColumnPage {
  items: VisitRequestSummary[]
  total: number
  loadedPages: number
  isLoadingMore: boolean
  loadMoreFailed: boolean
  // Bumped whenever the column's result set is replaced by a new query
  // (filter/search change), so the rendered column can remount and start
  // scrolled to the top. Refresh/polling keep it, preserving scroll.
  resetKey: number
}

type ColumnsState = Record<BoardStatus, BoardColumnPage>

export type FetchVisitRequestsPage = (params: ListVisitRequestsParams) => Promise<VisitRequestsPage>
export type ColumnQuery = Omit<ListVisitRequestsParams, 'status' | 'page' | 'pageSize'>

const EMPTY_COLUMN: BoardColumnPage = { items: [], total: 0, loadedPages: 0, isLoadingMore: false, loadMoreFailed: false, resetKey: 0 }

function appendUnique(existing: VisitRequestSummary[], incoming: VisitRequestSummary[]): VisitRequestSummary[] {
  const seen = new Set(existing.map((request) => request.id))
  return [...existing, ...incoming.filter((request) => !seen.has(request.id))]
}

// Refetches a column's already-loaded window in as few requests as the
// API's max page size allows: one call up to 100 rows, else 100-row pages.
async function fetchWindow(fetchPage: FetchVisitRequestsPage, query: ColumnQuery, status: BoardStatus, rows: number): Promise<VisitRequestsPage> {
  const apiStatus = API_STATUS_BY_BOARD_STATUS[status]
  if (rows <= API_MAX_PAGE_SIZE) {
    return fetchPage({ ...query, status: apiStatus, page: 1, pageSize: rows })
  }
  const pageCount = Math.ceil(rows / API_MAX_PAGE_SIZE)
  const pages = await Promise.all(
    Array.from({ length: pageCount }, (_, index) => fetchPage({ ...query, status: apiStatus, page: index + 1, pageSize: API_MAX_PAGE_SIZE })),
  )
  return {
    items: pages.reduce<VisitRequestSummary[]>((items, page) => appendUnique(items, page.items), []),
    total: pages[pages.length - 1].total,
  }
}

// Per-status paged columns for the invitations board: each column is its own
// server query (true totals, no column starved by another's newer rows), loads
// 20 at a time via `loadMore`, and `reload({ keepDepth: true })` re-queries
// what each column already shows so refresh/polling neither truncates a
// scrolled column nor jumps it back to the top.
export function usePagedBoardColumns(fetchPage: FetchVisitRequestsPage, query: ColumnQuery, visibleStatuses: readonly BoardStatus[]) {
  const [columns, setColumns] = useState<ColumnsState>({
    requested: EMPTY_COLUMN,
    approved: EMPTY_COLUMN,
    checked_in: EMPTY_COLUMN,
    denied: EMPTY_COLUMN,
  })

  const columnsRef = useRef(columns)
  const queryRef = useRef(query)
  const visibleStatusesRef = useRef(visibleStatuses)
  useEffect(() => {
    columnsRef.current = columns
  }, [columns])
  useEffect(() => {
    queryRef.current = query
    visibleStatusesRef.current = visibleStatuses
  }, [query, visibleStatuses])

  // `requestGeneration` discards any reload superseded by a newer one;
  // `resultSetGeneration` only moves when the result set is reset, so an
  // in-flight `loadMore` from the previous filter never appends into it.
  const requestGenerationRef = useRef(0)
  const resultSetGenerationRef = useRef(0)
  const isResettingRef = useRef(false)
  const loadingMoreRef = useRef(new Set<BoardStatus>())

  const reload = useCallback(
    async ({ keepDepth }: { keepDepth: boolean }) => {
      // A poll/refresh racing a filter reset would re-query the old depth
      // under the new filter; the reset is about to replace everything anyway.
      if (keepDepth && isResettingRef.current) return

      const generation = ++requestGenerationRef.current
      if (!keepDepth) {
        resultSetGenerationRef.current += 1
        isResettingRef.current = true
      }

      const currentQuery = queryRef.current
      const visible = visibleStatusesRef.current
      const current = columnsRef.current
      // A column mid-`loadMore` is left alone by a keep-depth reload so the
      // poll can't overwrite the page that's about to be appended.
      const statusesToFetch = BOARD_STATUSES.filter(
        (status) => visible.includes(status) && !(keepDepth && loadingMoreRef.current.has(status)),
      )

      try {
        const results = await Promise.all(
          statusesToFetch.map(async (status) => {
            const rows = keepDepth ? Math.max(1, current[status].loadedPages) * BOARD_PAGE_SIZE : BOARD_PAGE_SIZE
            return [status, await fetchWindow(fetchPage, currentQuery, status, rows)] as const
          }),
        )
        if (generation !== requestGenerationRef.current) return

        setColumns((previous) => {
          const next = { ...previous }
          for (const status of BOARD_STATUSES) {
            if (!visible.includes(status)) {
              next[status] = { ...EMPTY_COLUMN, resetKey: keepDepth ? previous[status].resetKey : previous[status].resetKey + 1 }
            }
          }
          for (const [status, page] of results) {
            next[status] = {
              ...previous[status],
              items: page.items,
              total: page.total,
              loadedPages: keepDepth ? Math.max(1, previous[status].loadedPages) : 1,
              loadMoreFailed: false,
              resetKey: keepDepth ? previous[status].resetKey : previous[status].resetKey + 1,
            }
          }
          return next
        })
      } finally {
        if (!keepDepth && generation === requestGenerationRef.current) {
          isResettingRef.current = false
        }
      }
    },
    [fetchPage],
  )

  const loadMore = useCallback(
    async (status: BoardStatus) => {
      const column = columnsRef.current[status]
      if (loadingMoreRef.current.has(status) || column.items.length >= column.total) return

      const resultSetGeneration = resultSetGenerationRef.current
      const nextPage = column.loadedPages + 1
      loadingMoreRef.current.add(status)
      setColumns((previous) => ({ ...previous, [status]: { ...previous[status], isLoadingMore: true, loadMoreFailed: false } }))

      try {
        const page = await fetchPage({
          ...queryRef.current,
          status: API_STATUS_BY_BOARD_STATUS[status],
          page: nextPage,
          pageSize: BOARD_PAGE_SIZE,
        })
        if (resultSetGeneration !== resultSetGenerationRef.current) return
        setColumns((previous) => {
          const items = appendUnique(previous[status].items, page.items)
          return {
            ...previous,
            [status]: {
              ...previous[status],
              items,
              // An empty page means rows left the status since `total` was
              // read; stop paging rather than requesting past the end forever.
              total: page.items.length === 0 ? items.length : page.total,
              loadedPages: nextPage,
            },
          }
        })
      } catch (error) {
        console.error('Failed to load more visit requests', error)
        if (resultSetGeneration === resultSetGenerationRef.current) {
          setColumns((previous) => ({ ...previous, [status]: { ...previous[status], loadMoreFailed: true } }))
        }
      } finally {
        loadingMoreRef.current.delete(status)
        setColumns((previous) => ({ ...previous, [status]: { ...previous[status], isLoadingMore: false } }))
      }
    },
    [fetchPage],
  )

  return { columns, reload, loadMore }
}
