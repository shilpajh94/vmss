import type { ReceptionDeskRepository } from '../repositories/reception-desk-repository'
import type { ReceptionDesk } from '../../domain/entities/reception-desk-schema'

export class ListReceptionDesksUseCase {
  private readonly receptionDeskRepository: ReceptionDeskRepository

  constructor(receptionDeskRepository: ReceptionDeskRepository) {
    this.receptionDeskRepository = receptionDeskRepository
  }

  async execute(): Promise<ReceptionDesk[]> {
    return this.receptionDeskRepository.list()
  }
}
