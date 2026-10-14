import type { KioskLocationValidationRepository } from '../repositories/kiosk-location-validation-repository'

export class UpdateKioskLocationValidationUseCase {
  private readonly kioskLocationValidationRepository: KioskLocationValidationRepository

  constructor(kioskLocationValidationRepository: KioskLocationValidationRepository) {
    this.kioskLocationValidationRepository = kioskLocationValidationRepository
  }

  async execute(enforce: boolean): Promise<boolean> {
    return this.kioskLocationValidationRepository.set(enforce)
  }
}
