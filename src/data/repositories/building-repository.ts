import type { Building, BuildingInput } from '../../domain/entities/building-schema'

export interface BuildingRepository {
  list(): Promise<Building[]>
  create(input: BuildingInput): Promise<Building>
  update(id: string, input: BuildingInput): Promise<Building>
  remove(id: string): Promise<void>
}
