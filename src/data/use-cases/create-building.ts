import type { BuildingRepository } from '../repositories/building-repository'
import type { Building, BuildingInput } from '../../domain/entities/building-schema'

export class CreateBuildingUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(input: BuildingInput): Promise<Building> {
    return this.buildingRepository.create(input)
  }
}
