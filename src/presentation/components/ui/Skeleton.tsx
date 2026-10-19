import type { ReactNode } from 'react'

// First-load placeholders (async-ui-states "A shared loading indicator
// represents in-progress async operations"). Each composed variant reuses
// the outer container classes of the real component it stands in for -
// border, radius, padding, header height - so the swap from skeleton to
// content doesn't move anything around it. The shimmer lives in index.css
// (`.skeleton`) and is disabled under prefers-reduced-motion.

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <span aria-hidden className={`skeleton block rounded-md ${className}`} />
}

// Screen readers get one "Loading…" announcement per placeholder region
// instead of nothing (the blocks themselves are aria-hidden).
function LoadingRegion({ label, className, children }: { label: string; className: string; children: ReactNode }) {
  return (
    <div role="status" aria-label={label} aria-busy="true" className={className}>
      {children}
    </div>
  )
}

// Enough rows to fill a typical viewport without promising more rows than
// a page may actually return (design.md D5).
const MAX_TABLE_ROWS = 8

// Varied bar widths so the placeholder reads as text, not a solid grid.
const CELL_WIDTHS = ['w-3/4', 'w-1/2', 'w-2/3', 'w-2/5', 'w-1/3', 'w-3/5']

interface TableSkeletonProps {
  columns: number
  rows?: number
  label?: string
}

// Same shell as the admin list tables (rounded-2xl bordered card, subtle
// header row with px-6 py-3.5 cells, px-6 py-4 body cells).
export function TableSkeleton({ columns, rows = MAX_TABLE_ROWS, label = 'Loading…' }: TableSkeletonProps) {
  const rowCount = Math.min(rows, MAX_TABLE_ROWS)
  return (
    <LoadingRegion label={label} className="w-full overflow-hidden rounded-2xl border border-border bg-surface">
      {/* Heights match the real tables: a 47px header row (py-3.5 around
          13px text) and 63px body rows (py-4 around the action buttons). */}
      <div className="flex h-[47px] items-center gap-6 bg-border-subtle px-4 md:px-6">
        {Array.from({ length: columns }, (_, column) => (
          <Skeleton key={column} className={`h-3 flex-1 ${column >= 2 ? 'max-md:hidden' : ''}`} />
        ))}
      </div>
      {Array.from({ length: rowCount }, (_, row) => (
        <div key={row} className="flex h-[63px] items-center gap-6 border-b border-border-subtle px-4 last:border-b-0 md:px-6">
          {Array.from({ length: columns }, (_, column) => (
            <div key={column} className={`flex-1 ${column >= 2 ? 'max-md:hidden' : ''}`}>
              <Skeleton className={`h-3.5 ${CELL_WIDTHS[(row + column) % CELL_WIDTHS.length]}`} />
            </div>
          ))}
        </div>
      ))}
    </LoadingRegion>
  )
}

interface ListSkeletonProps {
  rows?: number
  label?: string
}

// Stacked cards (activity feeds, audit entries, step lists).
export function ListSkeleton({ rows = 5, label = 'Loading…' }: ListSkeletonProps) {
  return (
    <LoadingRegion label={label} className="flex w-full flex-col gap-3">
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-4">
          <Skeleton className="size-10 shrink-0 rounded-full" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Skeleton className={`h-3.5 ${CELL_WIDTHS[row % CELL_WIDTHS.length]}`} />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </LoadingRegion>
  )
}

interface KpiRowSkeletonProps {
  count?: number
}

// Matches KpiRow's grid and tile (min-h-[132px], p-5).
export function KpiRowSkeleton({ count = 4 }: KpiRowSkeletonProps) {
  return (
    <LoadingRegion label="Loading summary…" className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-4">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex min-h-[132px] flex-col justify-between gap-4 rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="size-8 rounded-lg" />
          </div>
          <Skeleton className="h-7 w-16" />
        </div>
      ))}
    </LoadingRegion>
  )
}

interface CardSkeletonProps {
  className?: string
  bodyClassName?: string
}

// Matches ChartCard / dashboard cards (rounded-2xl, p-4 md:p-6, title row).
export function CardSkeleton({ className = '', bodyClassName = 'h-56' }: CardSkeletonProps) {
  return (
    <div aria-hidden className={`flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 ${className}`}>
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-4.5 w-40" />
        <Skeleton className="h-3 w-56 max-w-full" />
      </div>
      <Skeleton className={`w-full rounded-xl ${bodyClassName}`} />
    </div>
  )
}

interface CardGridSkeletonProps {
  count?: number
  className?: string
  cardClassName?: string
  label?: string
}

export function CardGridSkeleton({
  count = 4,
  className = 'grid w-full grid-cols-1 gap-4 md:gap-6 lg:grid-cols-2',
  cardClassName,
  label = 'Loading…',
}: CardGridSkeletonProps) {
  return (
    <LoadingRegion label={label} className={className}>
      {Array.from({ length: count }, (_, index) => (
        <CardSkeleton key={index} bodyClassName={cardClassName} />
      ))}
    </LoadingRegion>
  )
}

interface BoardSkeletonProps {
  columns?: number
  cardsPerColumn?: number
}

// Matches the invitation board's columns (BOARD_COLUMN_SIZING + its
// tinted header strip and stacked visit cards). Below `lg` only the first
// column shows, as the board itself shows one column at a time there.
export function BoardSkeleton({ columns = 4, cardsPerColumn = 3 }: BoardSkeletonProps) {
  return (
    <LoadingRegion label="Loading board…" className="flex min-h-0 w-full flex-1 items-stretch gap-3">
      {Array.from({ length: columns }, (_, column) => (
        <div key={column} className={`flex min-w-0 flex-1 flex-col gap-3 lg:min-w-[240px] lg:basis-0 ${column > 0 ? 'max-lg:hidden' : ''}`}>
          <div className="flex h-10 w-full items-center justify-between rounded-[10px] border-l-4 border-border bg-border-subtle px-4">
            <Skeleton className="h-3.5 w-24 bg-border" />
            <Skeleton className="h-4 w-6 rounded-full bg-border" />
          </div>
          {Array.from({ length: cardsPerColumn }, (_, card) => (
            <div key={card} className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
              <div className="flex items-center gap-3">
                <Skeleton className="size-9 shrink-0 rounded-full" />
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <Skeleton className={`h-3.5 ${CELL_WIDTHS[(column + card) % CELL_WIDTHS.length]}`} />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-3 w-2/3" />
            </div>
          ))}
        </div>
      ))}
    </LoadingRegion>
  )
}

interface FormSkeletonProps {
  rows?: number
  columns?: 1 | 2
  className?: string
  label?: string
  /** Omit the card chrome, for a region that already sits inside a card. */
  bare?: boolean
}

// Label-over-field rows, inside the same bordered surface card the admin
// settings/forms render in.
export function FormSkeleton({ rows = 4, columns = 2, className = '', label = 'Loading…', bare = false }: FormSkeletonProps) {
  const chrome = bare ? '' : 'rounded-2xl border border-border bg-surface p-4 md:p-6'
  return (
    <LoadingRegion label={label} className={`w-full ${chrome} ${className}`}>
      <div className={`grid gap-5 ${columns === 2 ? 'md:grid-cols-2' : ''}`}>
        {Array.from({ length: rows * columns }, (_, index) => (
          <div key={index} className="flex flex-col gap-2">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-11 w-full rounded-lg" />
          </div>
        ))}
      </div>
    </LoadingRegion>
  )
}
