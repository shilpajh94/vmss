import type { Kiosk } from '../../domain/entities/kiosk-schema'
import type { KioskRepository } from '../repositories/kiosk-repository'

export class SetKioskVisibilityUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(id: string, isHidden: boolean): Promise<Kiosk> {
    return this.kioskRepository.setHidden(id, isHidden)
  }
}
