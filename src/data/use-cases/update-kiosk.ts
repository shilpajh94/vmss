import type { Kiosk, KioskInput } from '../../domain/entities/kiosk-schema'
import type { KioskRepository } from '../repositories/kiosk-repository'

export class UpdateKioskUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(id: string, input: Partial<KioskInput>): Promise<Kiosk> {
    return this.kioskRepository.update(id, input)
  }
}
