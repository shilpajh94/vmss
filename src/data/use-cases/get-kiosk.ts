import type { Kiosk } from '../../domain/entities/kiosk-schema'
import type { KioskRepository } from '../repositories/kiosk-repository'

export class GetKioskUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(id: string): Promise<Kiosk> {
    return this.kioskRepository.get(id)
  }
}
