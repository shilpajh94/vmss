import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { DeviceRepository, DevicesPage, ListDevicesPageParams } from '../data/repositories/device-repository'
import { DeviceListResponseSchema, DeviceResponseSchema, type Device } from '../domain/entities/managed-device-schema'

export class HttpDeviceRepository implements DeviceRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async listPage(params: ListDevicesPageParams): Promise<DevicesPage> {
    const { operatingMode, page, pageSize, approvalStatus, status, branchId, buildingId, sortBy, sortOrder } = params
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_DEVICES,
      queryParams: { operatingMode, page, pageSize, approvalStatus, status, branchId, buildingId, sortBy, sortOrder },
      parserSchema: DeviceListResponseSchema,
    })

    return { items: response.data, total: response.pagination.total }
  }

  async approve(id: string): Promise<Device> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.APPROVE_DEVICE,
      pathParams: { id },
      parserSchema: DeviceResponseSchema,
    })

    return response.data
  }

  async enable(id: string): Promise<Device> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.ENABLE_DEVICE,
      pathParams: { id },
      parserSchema: DeviceResponseSchema,
    })

    return response.data
  }

  async disable(id: string): Promise<Device> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.DISABLE_DEVICE,
      pathParams: { id },
      parserSchema: DeviceResponseSchema,
    })

    return response.data
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_DEVICE,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}
