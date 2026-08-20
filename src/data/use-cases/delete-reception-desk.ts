import type { ReceptionDeskRepository } from '../repositories/reception-desk-repository'

export class DeleteReceptionDeskUseCase {
  private readonly receptionDeskRepository: ReceptionDeskRepository

  constructor(receptionDeskRepository: ReceptionDeskRepository) {
    this.receptionDeskRepository = receptionDeskRepository
  }

  async execute(id: string): Promise<void> {
    return this.receptionDeskRepository.remove(id)
  }
}
