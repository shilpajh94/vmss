import type { KiosksPage, ListKiosksPageParams } from '../repositories/kiosk-repository'
import type { KioskRepository } from '../repositories/kiosk-repository'

export class ListKiosksPageUseCase {
  private readonly kioskRepository: KioskRepository

  constructor(kioskRepository: KioskRepository) {
    this.kioskRepository = kioskRepository
  }

  async execute(params: ListKiosksPageParams): Promise<KiosksPage> {
    return this.kioskRepository.listPage(params)
  }
}
