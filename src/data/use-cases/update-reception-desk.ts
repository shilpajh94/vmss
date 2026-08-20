import type { ReceptionDeskRepository } from '../repositories/reception-desk-repository'
import type { ReceptionDesk, ReceptionDeskInput } from '../../domain/entities/reception-desk-schema'

export class UpdateReceptionDeskUseCase {
  private readonly receptionDeskRepository: ReceptionDeskRepository

  constructor(receptionDeskRepository: ReceptionDeskRepository) {
    this.receptionDeskRepository = receptionDeskRepository
  }

  async execute(id: string, input: ReceptionDeskInput): Promise<ReceptionDesk> {
    return this.receptionDeskRepository.update(id, input)
  }
}
