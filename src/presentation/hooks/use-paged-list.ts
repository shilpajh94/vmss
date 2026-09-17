import { useCallback, useState } from 'react'

// Shared page-number state for a server-paged list: next/prev navigation
// plus a `resetToFirstPage` a page's own filter-change handlers call, so
// changing a filter always re-anchors to page 1 instead of leaving the view
// on a page number the new, narrower result set may not even have.
// Request-building and filter state stay with each page's own hook, since
// those differ per entity - see design.md's "shared hook, not shared filter
// shape" decision.
export function usePagedList() {
  const [page, setPage] = useState(1)

  const goToNextPage = useCallback(() => setPage((current) => current + 1), [])
  const goToPrevPage = useCallback(() => setPage((current) => Math.max(1, current - 1)), [])
  const resetToFirstPage = useCallback(() => setPage(1), [])

  return { page, goToNextPage, goToPrevPage, resetToFirstPage, setPage }
}
