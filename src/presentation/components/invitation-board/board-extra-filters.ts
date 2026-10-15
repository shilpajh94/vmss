import { CircleDotIcon, ClipboardListIcon } from '../icons'
import type { BoardExtraFilter } from './BoardFilterBar'
import { SOURCE_FILTER_OPTIONS, STATUS_FILTER_OPTIONS } from './filter-options'

interface BoardExtraFilterState {
  statusFilter: string
  setStatusFilter: (value: string) => void
  sourceFilter: string
  setSourceFilter: (value: string) => void
}

// The Status and Source dropdowns both invitation boards add after
// Registration Type, built in one place so the staff and admin bars can't
// drift apart (align-staff-board-filters-with-admin).
export function boardExtraFilters({ statusFilter, setStatusFilter, sourceFilter, setSourceFilter }: BoardExtraFilterState): BoardExtraFilter[] {
  return [
    { icon: CircleDotIcon, value: statusFilter, options: STATUS_FILTER_OPTIONS, onChange: setStatusFilter, ariaLabel: 'Status' },
    { icon: ClipboardListIcon, value: sourceFilter, options: SOURCE_FILTER_OPTIONS, onChange: setSourceFilter, ariaLabel: 'Source' },
  ]
}
