import type { BuildingRepository, BuildingsPage, ListBuildingsPageParams } from '../repositories/building-repository'

export class ListBuildingsPageUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(params: ListBuildingsPageParams): Promise<BuildingsPage> {
    return this.buildingRepository.listPage(params)
  }
}
