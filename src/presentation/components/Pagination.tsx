import { ChevronLeftIcon, ChevronRightIcon } from './icons'

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPrev: () => void
  onNext: () => void
}

// Shared next/prev pagination control for any server-paged admin list.
// Extracted from staff-audit-trail's original page-local copy so every
// admin list page renders the same control instead of each hand-rolling
// its own - see design.md's "one shared pattern for paginated, server-
// filtered list" goal. No page-size selector yet (design.md Non-Goals).
export function Pagination({ page, pageSize, total, onPrev, onNext }: PaginationProps) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  const hasPrev = page > 1
  const hasNext = end < total

  return (
    <div className="flex w-full items-center justify-between border-t border-border pt-3">
      <p className="font-body text-[13px] text-text-muted">
        Showing {start}-{end} of {total} results
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={!hasPrev}
          aria-label="Previous page"
          className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface disabled:opacity-40"
        >
          <ChevronLeftIcon className="size-4 text-text" />
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!hasNext}
          aria-label="Next page"
          className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface disabled:opacity-40"
        >
          <ChevronRightIcon className="size-4 text-text" />
        </button>
      </div>
    </div>
  )
}
