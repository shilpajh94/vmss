import type { KioskRepository } from '../repositories/kiosk-repository'

export class DeleteKioskUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(id: string): Promise<void> {
    return this.kioskRepository.remove(id)
  }
}
