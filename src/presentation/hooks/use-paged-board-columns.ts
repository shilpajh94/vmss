import { useCallback, useEffect, useRef, useState } from 'react'
import type { ListVisitRequestsParams, VisitRequestsPage } from '../../data/repositories/visit-request-summary-repository'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'

export type BoardStatus = 'requested' | 'approved' | 'checked_in' | 'checked_out' | 'denied' | 'archived'

const BOARD_STATUSES: readonly BoardStatus[] = ['requested', 'approved', 'checked_in', 'checked_out', 'denied', 'archived']

// Board column -> the `status` value `GET /invitations` filters on. A
// workflow invitation stays `submitted` until its last step clears (see
// board-sticky-headers-lazy-load design.md Decision 2), so each column is
// exactly one server-side status query.
const API_STATUS_BY_BOARD_STATUS: Record<BoardStatus, string> = {
  requested: 'submitted',
  approved: 'approved',
  checked_in: 'checked_in',
  checked_out: 'checked_out',
  denied: 'denied',
  archived: 'archived',
}

export function boardStatusForApiStatus(apiStatus: string): BoardStatus | undefined {
  return BOARD_STATUSES.find((status) => API_STATUS_BY_BOARD_STATUS[status] === apiStatus)
}

export const BOARD_PAGE_SIZE = 20
const API_MAX_PAGE_SIZE = 100

// Each column lists what most recently entered its status first (a fresh
// check-in tops Checked-in even if it was submitted last week), not the
// API's default submission order. Every column fetch goes through
// `columnPageParams` so no load path can drop it.
const BOARD_SORT = { sortBy: 'status_changed_at', sortOrder: 'desc' } as const

// The API takes one purpose / type / source per request, so a column with
// several selected values is queried once per combination and merged. A visit
// request has exactly one value for each, so combinations never overlap.
export const MAX_FILTER_COMBINATIONS = 48

type SingleValueQuery = Omit<ColumnQuery, 'purposesOfVisit' | 'registrationTypes' | 'sources'> &
  Pick<ListVisitRequestsParams, 'purposeOfVisit' | 'registrationType' | 'source'>

export function filterCombinations(query: ColumnQuery): SingleValueQuery[] {
  const { purposesOfVisit = [], registrationTypes = [], sources = [], ...rest } = query
  let dimensions = [purposesOfVisit, registrationTypes, sources]
  // Past the cap, widen the largest dimension to "any" rather than send
  // dozens of requests per column.
  while (dimensions.reduce((count, values) => count * Math.max(1, values.length), 1) > MAX_FILTER_COMBINATIONS) {
    const largest = dimensions.reduce((best, values) => (values.length > best.length ? values : best))
    dimensions = dimensions.map((values) => (values === largest ? [] : values))
  }
  const [purposes, types, origins] = dimensions.map((values): (string | undefined)[] => (values.length > 0 ? values : [undefined]))
  return purposes.flatMap((purposeOfVisit) =>
    types.flatMap((registrationType) => origins.map((source) => ({ ...rest, purposeOfVisit, registrationType, source }))),
  )
}

function columnPageParams(query: SingleValueQuery, status: BoardStatus, page: number, pageSize: number): ListVisitRequestsParams {
  return { ...query, ...BOARD_SORT, status: API_STATUS_BY_BOARD_STATUS[status], page, pageSize }
}

// The list payload doesn't expose `status_changed_at`, so combinations can't
// be sorted against each other; interleaving by rank keeps each combination's
// own newest-first order and approximates the global one.
function interleave(pages: VisitRequestSummary[][]): VisitRequestSummary[] {
  const longest = Math.max(0, ...pages.map((items) => items.length))
  const merged: VisitRequestSummary[] = []
  for (let rank = 0; rank < longest; rank += 1) {
    for (const items of pages) {
      if (rank < items.length) merged.push(items[rank])
    }
  }
  return appendUnique([], merged)
}

// One page of a column across every filter combination, merged
// in rank order. Totals add up exactly because combinations are disjoint.
async function fetchColumnPage(
  fetchPage: FetchVisitRequestsPage,
  query: ColumnQuery,
  status: BoardStatus,
  page: number,
  pageSize: number,
): Promise<VisitRequestsPage> {
  const combinations = filterCombinations(query)
  const pages = await Promise.all(combinations.map((combination) => fetchPage(columnPageParams(combination, status, page, pageSize))))
  if (pages.length === 1) return pages[0]
  return { items: interleave(pages.map((current) => current.items)), total: pages.reduce((sum, current) => sum + current.total, 0) }
}

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
export type ColumnQuery = Omit<
  ListVisitRequestsParams,
  'status' | 'page' | 'pageSize' | 'sortBy' | 'sortOrder' | 'purposeOfVisit' | 'registrationType' | 'source'
> & {
  purposesOfVisit?: string[]
  registrationTypes?: string[]
  sources?: string[]
}

const EMPTY_COLUMN: BoardColumnPage = { items: [], total: 0, loadedPages: 0, isLoadingMore: false, loadMoreFailed: false, resetKey: 0 }

function appendUnique(existing: VisitRequestSummary[], incoming: VisitRequestSummary[]): VisitRequestSummary[] {
  const seen = new Set(existing.map((request) => request.id))
  return [...existing, ...incoming.filter((request) => !seen.has(request.id))]
}

// Refetches a column's already-loaded window in as few requests as the
// API's max page size allows: one call up to 100 rows, else 100-row pages.
async function fetchWindow(fetchPage: FetchVisitRequestsPage, query: ColumnQuery, status: BoardStatus, rows: number): Promise<VisitRequestsPage> {
  if (rows <= API_MAX_PAGE_SIZE) {
    return fetchColumnPage(fetchPage, query, status, 1, rows)
  }
  const pageCount = Math.ceil(rows / API_MAX_PAGE_SIZE)
  const pages = await Promise.all(
    Array.from({ length: pageCount }, (_, index) => fetchColumnPage(fetchPage, query, status, index + 1, API_MAX_PAGE_SIZE)),
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
    checked_out: EMPTY_COLUMN,
    denied: EMPTY_COLUMN,
    archived: EMPTY_COLUMN,
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
        const page = await fetchColumnPage(fetchPage, queryRef.current, status, nextPage, BOARD_PAGE_SIZE)
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
