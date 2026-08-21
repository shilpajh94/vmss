import type { FloorRepository } from '../repositories/floor-repository'
import type { Floor, FloorInput } from '../../domain/entities/floor-schema'

export class CreateFloorUseCase {
  private readonly floorRepository: FloorRepository

  constructor(floorRepository: FloorRepository) {
    this.floorRepository = floorRepository
  }

  async execute(input: FloorInput): Promise<Floor> {
    return this.floorRepository.create(input)
  }
}
