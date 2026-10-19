import type { ListDevicesPageParams } from '../../../data/repositories/device-repository'

export type DeviceStatusFilter = '' | 'pending' | 'approved' | 'disabled'

export const DEVICE_STATUS_OPTIONS: { value: Exclude<DeviceStatusFilter, ''>; label: string }[] = [
  { value: 'pending', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'disabled', label: 'Disabled' },
]

// The API has no separate pending list: the UI's three status options map onto
// `approvalStatus` + `status` query parameters.
export function statusFilterToQuery(filter: DeviceStatusFilter): Pick<ListDevicesPageParams, 'approvalStatus' | 'status'> {
  switch (filter) {
    case 'pending':
      return { approvalStatus: 'pending' }
    case 'approved':
      return { approvalStatus: 'approved', status: 'active' }
    case 'disabled':
      return { approvalStatus: 'approved', status: 'inactive' }
    default:
      return {}
  }
}

export type DeviceSort =
  | 'name:asc'
  | 'name:desc'
  | 'created_at:desc'
  | 'created_at:asc'
  | 'approval_status:asc'
  | 'approval_status:desc'

export const DEVICE_SORT_OPTIONS: { value: DeviceSort; label: string }[] = [
  { value: 'name:asc', label: 'Name (A–Z)' },
  { value: 'name:desc', label: 'Name (Z–A)' },
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc', label: 'Oldest first' },
  { value: 'approval_status:asc', label: 'Approval status (A–Z)' },
  { value: 'approval_status:desc', label: 'Approval status (Z–A)' },
]

export function parseDeviceSort(sort: DeviceSort): Pick<ListDevicesPageParams, 'sortBy' | 'sortOrder'> {
  const [sortBy, sortOrder] = sort.split(':') as [ListDevicesPageParams['sortBy'], ListDevicesPageParams['sortOrder']]
  return { sortBy, sortOrder }
}
