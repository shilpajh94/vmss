export interface DropdownOption {
  value: string
  label: string
}

export const PAGE_SIZE = 8

export const DATE_RANGE_OPTIONS: DropdownOption[] = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'all_time', label: 'All time' },
]

export const ACTIVITY_TYPE_OPTIONS: DropdownOption[] = [
  { value: 'all', label: 'All Activities' },
  { value: 'check_in', label: 'Check-in' },
  { value: 'check_out', label: 'Check-out' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'modified', label: 'Modified' },
  { value: 'escalated', label: 'Escalated' },
]

export const DEFAULT_DATE_RANGE = DATE_RANGE_OPTIONS[1].value
export const DEFAULT_ACTIVITY_TYPE = ACTIVITY_TYPE_OPTIONS[0].value
