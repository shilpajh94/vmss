import { CircleDotIcon, ClipboardListIcon } from '../icons'
import type { BoardExtraFilter } from './BoardFilterBar'
import { SOURCE_OPTIONS, STATUS_OPTIONS } from './filter-options'

interface BoardExtraFilterState {
  statusFilter: string[]
  setStatusFilter: (values: string[]) => void
  sourceFilter: string[]
  setSourceFilter: (values: string[]) => void
}

// The Status and Source dropdowns both invitation boards add after
// Registration Type, built in one place so the staff and admin bars can't
// drift apart (align-staff-board-filters-with-admin).
export function boardExtraFilters({ statusFilter, setStatusFilter, sourceFilter, setSourceFilter }: BoardExtraFilterState): BoardExtraFilter[] {
  return [
    { icon: CircleDotIcon, values: statusFilter, options: STATUS_OPTIONS, onChange: setStatusFilter, allLabel: 'All statuses', ariaLabel: 'Status' },
    { icon: ClipboardListIcon, values: sourceFilter, options: SOURCE_OPTIONS, onChange: setSourceFilter, allLabel: 'All sources', ariaLabel: 'Source' },
  ]
}
