import type { FloorRepository } from '../repositories/floor-repository'
import type { Floor, FloorInput } from '../../domain/entities/floor-schema'

export class UpdateFloorUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(id: string, input: FloorInput): Promise<Floor> {
    return this.floorRepository.update(id, input)
  }
}
