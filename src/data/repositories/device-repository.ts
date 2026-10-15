import type { Device, DeviceApprovalStatus, DeviceOperatingMode } from '../../domain/entities/managed-device-schema'

export interface ListDevicesPageParams {
  operatingMode: DeviceOperatingMode
  page: number
  pageSize: number
  approvalStatus?: DeviceApprovalStatus
  status?: 'active' | 'inactive'
  branchId?: string
  buildingId?: string
  sortBy: 'name' | 'created_at' | 'approval_status'
  sortOrder: 'asc' | 'desc'
}

export interface DevicesPage {
  items: Device[]
  total: number
}

export interface DeviceRepository {
  listPage(params: ListDevicesPageParams): Promise<DevicesPage>
  approve(id: string): Promise<Device>
  enable(id: string): Promise<Device>
  disable(id: string): Promise<Device>
  remove(id: string): Promise<void>
}
