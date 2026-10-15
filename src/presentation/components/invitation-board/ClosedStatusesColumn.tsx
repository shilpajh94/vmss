import { useId, type ReactNode } from 'react'
import { ACCENT_CLASSES, BOARD_COLUMN_SIZING } from './KanbanColumn'

interface ClosedStatusEntry {
  status: string
  label: string
  total: number
}

interface ClosedStatusesColumnProps {
  statuses: ClosedStatusEntry[]
  selectedStatus: string
  onSelect: (status: string) => void
  /** The selected status's column, rendered embedded (no header of its own). */
  children: ReactNode
}

function accentFor(status: string) {
  return ACCENT_CLASSES[status as keyof typeof ACCENT_CLASSES] ?? ACCENT_CLASSES.checked_out
}

// Checked-out, Denied, and Archived share one desktop column (staff-dashboard
// "Closed statuses share one column on desktop"): they're mostly look-ups, so
// they get one column's width instead of three. The segmented switcher is the
// column's header - no title row - kept at the other headers' 40px so every
// column's first card lines up, and tinted in the selected status's accent.
export function ClosedStatusesColumn({ statuses, selectedStatus, onSelect, children }: ClosedStatusesColumnProps) {
  const idPrefix = useId()
  const selectedAccent = accentFor(selectedStatus)

  return (
    <div className={`${BOARD_COLUMN_SIZING} gap-3`}>
      {/* Stacked label-over-count segments: a single "label count" row needs
          ~250px and won't fit the 240px column floor. Segments are
          content-sized (not equal thirds), so "Checked-out" gets the room it
          needs and the shorter labels share the rest. 3px padding + 4px
          segment padding + two 13px lines = the 40px header height. */}
      <div
        role="tablist"
        aria-label="Closed status"
        className={`flex h-10 w-full shrink-0 gap-[3px] rounded-[10px] border-l-4 p-[3px] transition-colors ${selectedAccent.border} ${selectedAccent.tint}`}
      >
        {statuses.map((entry) => {
          const isSelected = entry.status === selectedStatus
          const accent = accentFor(entry.status)
          return (
            <button
              key={entry.status}
              id={`${idPrefix}-tab-${entry.status}`}
              type="button"
              role="tab"
              aria-selected={isSelected}
              aria-controls={`${idPrefix}-panel`}
              aria-label={`${entry.label}, ${entry.total}`}
              onClick={() => onSelect(entry.status)}
              className={`flex min-w-0 flex-auto flex-col items-center justify-center rounded-[7px] px-1.5 py-1 font-body text-[11px] leading-[13px] transition-colors focus-visible:ring-2 focus-visible:ring-secondary-accent/40 focus-visible:outline-none ${
                isSelected ? 'bg-surface shadow-sm' : 'text-text-muted hover:bg-surface/60'
              }`}
            >
              <span className={`w-full truncate text-center font-semibold ${isSelected ? 'text-text' : ''}`}>{entry.label}</span>
              <span className={`font-bold ${isSelected ? accent.text : ''}`}>{entry.total}</span>
            </button>
          )
        })}
      </div>

      <div
        id={`${idPrefix}-panel`}
        role="tabpanel"
        aria-labelledby={`${idPrefix}-tab-${selectedStatus}`}
        className="flex min-h-0 w-full flex-1 flex-col"
      >
        {children}
      </div>
    </div>
  )
}
