import type { Building, BuildingInput } from '../../domain/entities/building-schema'
import type { ListOptions } from './list-options'

export interface ListBuildingsPageParams {
  page: number
  pageSize: number
  status?: 'active' | 'inactive'
  /** No `branchId` query param exists on this endpoint - sent as `X-Branch-ID` instead. */
  branchId?: string
}

export interface BuildingsPage {
  items: Building[]
  total: number
}

export interface BuildingRepository {
  list(options?: ListOptions): Promise<Building[]>
  listPage(params: ListBuildingsPageParams): Promise<BuildingsPage>
  create(input: BuildingInput): Promise<Building>
  update(id: string, input: BuildingInput): Promise<Building>
  remove(id: string): Promise<void>
}
