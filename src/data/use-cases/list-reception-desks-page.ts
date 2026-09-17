import type {
  ListReceptionDesksPageParams,
  ReceptionDeskRepository,
  ReceptionDesksPage,
} from '../repositories/reception-desk-repository'

export class ListReceptionDesksPageUseCase {
  private readonly receptionDeskRepository: ReceptionDeskRepository

  constructor(receptionDeskRepository: ReceptionDeskRepository) {
    this.receptionDeskRepository = receptionDeskRepository
  }

  async execute(params: ListReceptionDesksPageParams): Promise<ReceptionDesksPage> {
    return this.receptionDeskRepository.listPage(params)
  }
}
