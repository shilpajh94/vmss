import type { DeviceRepository } from '../repositories/device-repository'

export class DeleteDeviceUseCase {
  private readonly deviceRepository: DeviceRepository

  constructor(deviceRepository: DeviceRepository) {
    this.deviceRepository = deviceRepository
  }

  async execute(id: string): Promise<void> {
    return this.deviceRepository.remove(id)
  }
}
