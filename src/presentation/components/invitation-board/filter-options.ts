import type { DropdownOption } from '../ui/DropdownFilter'
import type { InvitationExportFormat } from '../../../data/repositories/visit-request-summary-repository'
import { todayAsDateInputValue } from '../../utils/local-date-input-value'

// Values are the API's own status/source values, so they pass straight
// through as query params. Shared by the admin board's filter bar and the
// Export invitations dialog so their labels can't drift apart.
export const STATUS_OPTIONS: DropdownOption[] = [
  { value: 'submitted', label: 'Requested' },
  { value: 'approved', label: 'Approved' },
  { value: 'checked_in', label: 'Checked-in' },
  { value: 'checked_out', label: 'Checked-out' },
  { value: 'denied', label: 'Denied' },
]

export const SOURCE_OPTIONS: DropdownOption[] = [
  { value: 'staff_pre_registration', label: 'Staff Pre-Registration' },
  { value: 'visitor_walk_in', label: 'Visitor Walk-in' },
]

export const REGISTRATION_TYPE_OPTIONS: DropdownOption[] = [
  { value: 'individual', label: 'Individual' },
  { value: 'group', label: 'Group' },
]

export const STATUS_FILTER_OPTIONS: DropdownOption[] = [{ value: '', label: 'All statuses' }, ...STATUS_OPTIONS]

export const SOURCE_FILTER_OPTIONS: DropdownOption[] = [{ value: '', label: 'All sources' }, ...SOURCE_OPTIONS]

// Mirrors the API's status-to-timestamp mapping for the export's date range
// (VMSS_API add-invitation-export, design.md Decision 3); '' is "All statuses".
const EXPORT_DATE_LABELS: Record<string, string> = {
  '': 'Created date',
  submitted: 'Submitted date',
  approved: 'Approval date',
  denied: 'Denial date',
  checked_in: 'Check-in date',
  checked_out: 'Check-out date',
}

export function exportDateLabel(status: string): string {
  return EXPORT_DATE_LABELS[status] ?? EXPORT_DATE_LABELS['']
}

export function optionLabel(options: DropdownOption[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? value
}

// Built client-side: the API's own `Content-Disposition` filename isn't
// readable cross-origin (it sets no CORS `expose_headers`).
export function exportFilename(status: string, format: InvitationExportFormat): string {
  return `invitations-${status || 'all'}-${todayAsDateInputValue().replaceAll('-', '')}.${format}`
}
