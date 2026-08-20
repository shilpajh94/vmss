import type { Floor, FloorInput } from '../../domain/entities/floor-schema'

export interface FloorRepository {
  list(buildingId?: string): Promise<Floor[]>
  create(input: FloorInput): Promise<Floor>
  update(id: string, input: FloorInput): Promise<Floor>
  remove(id: string): Promise<void>
}
