import { useEffect, useState, type ReactNode } from 'react'
import { useIsDesktop } from '../../hooks/use-media-query'
import { useStoredState } from '../../hooks/use-stored-state'
import { ClosedStatusesColumn } from './ClosedStatusesColumn'

interface BoardColumn {
  status: string
  label: string
  requests: ReadonlyArray<unknown>
  /** Server total for the status; shown on the mobile tabs instead of the loaded count. */
  total: number
}

export interface ColumnRenderOptions {
  /** True inside the Closed column's tab panel, which supplies the header and sizing. */
  embedded: boolean
}

interface ResponsiveBoardProps<TColumn extends BoardColumn> {
  /** Namespaces the remembered Closed-column selection, so each board keeps its own. */
  boardKey: 'staff' | 'admin'
  columns: TColumn[]
  /** Statuses grouped into the desktop Closed column, in switcher order; the first is the default. */
  closedStatuses: readonly string[]
  /** A closed status the status filter just picked; the Closed column switches to it. */
  focusClosedStatus?: string
  renderColumn: (column: TColumn, options: ColumnRenderOptions) => ReactNode
}

const STANDALONE: ColumnRenderOptions = { embedded: false }
const EMBEDDED: ColumnRenderOptions = { embedded: true }

// From `lg` up the working statuses render as side-by-side columns and the
// closed ones share a single Closed column behind a switcher (staff-dashboard
// "Closed statuses share one column on desktop"). Below it, one column at a
// time is shown full width behind a status selector with each column's count
// (responsive-layout "Invitation Boards Show One Status Column at a Time
// Below Desktop"). Switching only changes which already-loaded column
// renders — no refetch, and filters are untouched.
// On desktop the board fills the height it's given and each column scrolls
// internally, so column headers never scroll out of view. Below `lg` the page
// scrolls as one (a tall stacked header would otherwise squeeze the list to a
// sliver) and the status tabs are sticky instead.
export function ResponsiveBoard<TColumn extends BoardColumn>({
  boardKey,
  columns,
  closedStatuses,
  focusClosedStatus,
  renderColumn,
}: ResponsiveBoardProps<TColumn>) {
  const isDesktop = useIsDesktop()
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>(undefined)
  const [closedStatus, setClosedStatus] = useStoredState<string>(
    `vmss:ui:board:${boardKey}:closed-status`,
    closedStatuses[0] ?? '',
    (raw) => (typeof raw === 'string' && closedStatuses.includes(raw) ? raw : undefined),
  )

  // Picking a closed status in the filter is the user's latest choice of
  // one, so it is remembered like a switcher click.
  useEffect(() => {
    if (focusClosedStatus && closedStatuses.includes(focusClosedStatus)) setClosedStatus(focusClosedStatus)
  }, [focusClosedStatus, closedStatuses, setClosedStatus])

  if (isDesktop) {
    const workingColumns = columns.filter((column) => !closedStatuses.includes(column.status))
    const closedColumns = closedStatuses
      .map((status) => columns.find((column) => column.status === status))
      .filter((column): column is TColumn => column !== undefined)
    const selectedClosedColumn = closedColumns.find((column) => column.status === closedStatus) ?? closedColumns[0]

    return (
      <div className="scrollbar-thin flex min-h-0 w-full flex-1 items-stretch gap-3 overflow-x-auto">
        {workingColumns.map((column) => renderColumn(column, STANDALONE))}
        {selectedClosedColumn ? (
          <ClosedStatusesColumn statuses={closedColumns} selectedStatus={selectedClosedColumn.status} onSelect={setClosedStatus}>
            {renderColumn(selectedClosedColumn, EMBEDDED)}
          </ClosedStatusesColumn>
        ) : null}
      </div>
    )
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
      {activeColumn ? renderColumn(activeColumn, STANDALONE) : null}
    </div>
  )
}
