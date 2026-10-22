import type { BuildingRepository } from '../repositories/building-repository'
import type { Building } from '../../domain/entities/building-schema'
import type { ListOptions } from '../repositories/list-options'

export class ListBuildingsUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(options?: ListOptions): Promise<Building[]> {
    return this.buildingRepository.list(options)
  }
}
