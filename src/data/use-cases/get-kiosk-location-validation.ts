import type { KioskLocationValidationRepository } from '../repositories/kiosk-location-validation-repository'

export class GetKioskLocationValidationUseCase {
  private readonly kioskLocationValidationRepository: KioskLocationValidationRepository

  constructor(kioskLocationValidationRepository: KioskLocationValidationRepository) {
    this.kioskLocationValidationRepository = kioskLocationValidationRepository
  }

  async execute(): Promise<boolean> {
    return this.kioskLocationValidationRepository.get()
  }
}
