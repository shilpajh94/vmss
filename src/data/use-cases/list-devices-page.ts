import type { DeviceRepository, DevicesPage, ListDevicesPageParams } from '../repositories/device-repository'

export class ListDevicesPageUseCase {
  private readonly deviceRepository: DeviceRepository

  constructor(deviceRepository: DeviceRepository) {
    this.deviceRepository = deviceRepository
  }

  async execute(params: ListDevicesPageParams): Promise<DevicesPage> {
    return this.deviceRepository.listPage(params)
  }
}
