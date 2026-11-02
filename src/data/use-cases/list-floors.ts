import type { FloorRepository } from '../repositories/floor-repository'
import type { Floor } from '../../domain/entities/floor-schema'
import type { ListOptions } from '../repositories/list-options'

export class ListFloorsUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(buildingId?: string, options?: ListOptions): Promise<Floor[]> {
    return this.floorRepository.list(buildingId, options)
  }
}
