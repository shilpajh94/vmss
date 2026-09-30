import type { Kiosk, KioskInput } from '../../domain/entities/kiosk-schema'
import type { KioskRepository } from '../repositories/kiosk-repository'

export class CreateKioskUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(input: KioskInput): Promise<Kiosk> {
    return this.kioskRepository.create(input)
  }
}
