import type { FloorRepository } from '../repositories/floor-repository'

export class DeleteFloorUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(id: string): Promise<void> {
    return this.floorRepository.remove(id)
  }
}
