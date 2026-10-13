import { useState, type ReactNode } from 'react'
import { useIsDesktop } from '../../hooks/use-media-query'

interface BoardColumn {
  status: string
  label: string
  requests: ReadonlyArray<unknown>
  /** Server total for the status; shown on the mobile tabs instead of the loaded count. */
  total: number
}

interface ResponsiveBoardProps<TColumn extends BoardColumn> {
  columns: TColumn[]
  renderColumn: (column: TColumn) => ReactNode
}

// From `lg` up every status column renders side by side, as before. Below
// it, one column at a time is shown full width behind a status selector
// with each column's count (responsive-layout "Invitation Boards Show One
// Status Column at a Time Below Desktop"). Switching only changes which
// already-loaded column renders — no refetch, and filters are untouched.
// On desktop the board fills the height it's given and each column scrolls
// internally, so column headers never scroll out of view. Below `lg` the page
// scrolls as one (a tall stacked header would otherwise squeeze the list to a
// sliver) and the status tabs are sticky instead.
export function ResponsiveBoard<TColumn extends BoardColumn>({ columns, renderColumn }: ResponsiveBoardProps<TColumn>) {
  const isDesktop = useIsDesktop()
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>(undefined)

  if (isDesktop) {
    return <div className="flex min-h-0 w-full flex-1 items-stretch gap-4 overflow-x-auto">{columns.map(renderColumn)}</div>
  }

  // Until the user picks one, open on the first column that has cards.
  const activeColumn =
    columns.find((column) => column.status === selectedStatus) ??
    columns.find((column) => column.total > 0) ??
    columns[0]

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col gap-4">
      {/* Sticks flush to <main>'s top edge: a plain `top-0` would stop at its
          page padding and leave a strip where cards show through. The matching
          padding/negative margin (= p-page-content, = the section gap above)
          fills that strip with background and leaves the resting layout as is. */}
      <div
        role="tablist"
        aria-label="Visit status"
        className="scrollbar-thin sticky -top-4 z-10 -mx-1 -mt-4 flex shrink-0 gap-2 overflow-x-auto bg-bg px-1 pt-4 pb-1 md:-top-6 md:-mt-6 md:pt-6"
      >
        {columns.map((column) => {
          const isActive = column.status === activeColumn?.status
          return (
            <button
              key={column.status}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setSelectedStatus(column.status)}
              className={`flex min-h-10 shrink-0 items-center gap-2 rounded-full border px-4 font-body text-[13px] font-semibold whitespace-nowrap transition-colors ${
                isActive ? 'border-primary bg-primary text-white' : 'border-border bg-surface text-text'
              }`}
            >
              {column.label}
              <span
                className={`rounded-full px-1.5 py-0.5 text-[11px] font-bold ${isActive ? 'bg-white/20 text-white' : 'bg-border-subtle text-text-muted'}`}
              >
                {column.total}
              </span>
            </button>
          )
        })}
      </div>
      {activeColumn ? renderColumn(activeColumn) : null}
    </div>
  )
}
