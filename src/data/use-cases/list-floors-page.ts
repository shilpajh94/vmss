import type { FloorRepository, FloorsPage, ListFloorsPageParams } from '../repositories/floor-repository'

export class ListFloorsPageUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(params: ListFloorsPageParams): Promise<FloorsPage> {
    return this.floorRepository.listPage(params)
  }
}
