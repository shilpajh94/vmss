import type { BuildingRepository } from '../repositories/building-repository'
import type { Building, BuildingInput } from '../../domain/entities/building-schema'

export class UpdateBuildingUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(id: string, input: BuildingInput): Promise<Building> {
    return this.buildingRepository.update(id, input)
  }
}
