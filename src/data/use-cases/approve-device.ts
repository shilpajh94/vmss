import type { Device } from '../../domain/entities/managed-device-schema'
import type { DeviceRepository } from '../repositories/device-repository'

export class ApproveDeviceUseCase {
  private readonly deviceRepository: DeviceRepository

  constructor(deviceRepository: DeviceRepository) {
    this.deviceRepository = deviceRepository
  }

  async execute(id: string): Promise<Device> {
    return this.deviceRepository.approve(id)
  }
}
