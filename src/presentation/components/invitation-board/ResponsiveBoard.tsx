import { useState, type ReactNode } from 'react'
import { useIsDesktop } from '../../hooks/use-media-query'

interface BoardColumn {
  status: string
  label: string
  requests: ReadonlyArray<unknown>
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
export function ResponsiveBoard<TColumn extends BoardColumn>({ columns, renderColumn }: ResponsiveBoardProps<TColumn>) {
  const isDesktop = useIsDesktop()
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>(undefined)

  if (isDesktop) {
    return <div className="flex w-full flex-1 items-start gap-4 overflow-x-auto">{columns.map(renderColumn)}</div>
  }

  // Until the user picks one, open on the first column that has cards.
  const activeColumn =
    columns.find((column) => column.status === selectedStatus) ??
    columns.find((column) => column.requests.length > 0) ??
    columns[0]

  return (
    <div className="flex w-full flex-1 flex-col gap-4">
      <div role="tablist" aria-label="Visit status" className="scrollbar-thin -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
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
                {column.requests.length}
              </span>
            </button>
          )
        })}
      </div>
      {activeColumn ? renderColumn(activeColumn) : null}
    </div>
  )
}
