import type { FloorRepository } from '../repositories/floor-repository'
import type { Floor } from '../../domain/entities/floor-schema'

export class ListFloorsUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(buildingId?: string): Promise<Floor[]> {
    return this.floorRepository.list(buildingId)
  }
}
