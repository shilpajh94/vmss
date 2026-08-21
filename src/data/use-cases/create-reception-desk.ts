import type { ReceptionDeskRepository } from '../repositories/reception-desk-repository'
import type { ReceptionDesk, ReceptionDeskInput } from '../../domain/entities/reception-desk-schema'

export class CreateReceptionDeskUseCase {
  private readonly receptionDeskRepository: ReceptionDeskRepository

  constructor(receptionDeskRepository: ReceptionDeskRepository) {
    this.receptionDeskRepository = receptionDeskRepository
  }

  async execute(input: ReceptionDeskInput): Promise<ReceptionDesk> {
    return this.receptionDeskRepository.create(input)
  }
}
