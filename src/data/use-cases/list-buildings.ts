import type { BuildingRepository } from '../repositories/building-repository'
import type { Building } from '../../domain/entities/building-schema'

export class ListBuildingsUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(): Promise<Building[]> {
    return this.buildingRepository.list()
  }
}
