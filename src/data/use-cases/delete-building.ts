import type { BuildingRepository } from '../repositories/building-repository'

export class DeleteBuildingUseCase {
  private readonly buildingRepository: BuildingRepository

  constructor(buildingRepository: BuildingRepository) {
    this.buildingRepository = buildingRepository
  }

  async execute(id: string): Promise<void> {
    return this.buildingRepository.remove(id)
  }
}
