import type { DropdownOption } from '../../components/ui/DropdownFilter'

export type { DropdownOption }

export const PAGE_SIZE = 8

export const DATE_RANGE_OPTIONS: DropdownOption[] = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'all_time', label: 'All time' },
]

export const ACTIVITY_TYPE_OPTIONS: DropdownOption[] = [
  { value: 'all', label: 'All Activities' },
  { value: 'invitation_created', label: 'Invitation Created' },
  { value: 'walk_in_registration_created', label: 'Walk-in Registered' },
  { value: 'invitation_approved', label: 'Invitation Approved' },
  { value: 'invitation_approval_step_approved', label: 'Approval Step Approved' },
  { value: 'invitation_checked_in_public', label: 'Checked In' },
  { value: 'invitation_rescheduled', label: 'Rescheduled' },
]

export const DEFAULT_DATE_RANGE = DATE_RANGE_OPTIONS[1].value
export const DEFAULT_ACTIVITY_TYPE = ACTIVITY_TYPE_OPTIONS[0].value
