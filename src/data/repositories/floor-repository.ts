import type { Floor, FloorInput } from '../../domain/entities/floor-schema'
import type { ListOptions } from './list-options'

export interface ListFloorsPageParams {
  page: number
  pageSize: number
  buildingId?: string
  status?: 'active' | 'inactive'
  accessLevel?: 'public' | 'restricted' | 'secure'
}

export interface FloorsPage {
  items: Floor[]
  total: number
}

export interface FloorRepository {
  list(buildingId?: string, options?: ListOptions): Promise<Floor[]>
  listPage(params: ListFloorsPageParams): Promise<FloorsPage>
  create(input: FloorInput): Promise<Floor>
  update(id: string, input: FloorInput): Promise<Floor>
  remove(id: string): Promise<void>
}
