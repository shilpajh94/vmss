import type { ReceptionDesk, ReceptionDeskInput } from '../../domain/entities/reception-desk-schema'

export interface ListReceptionDesksPageParams {
  page: number
  pageSize: number
  floorId?: string
  status?: 'active' | 'maintenance' | 'inactive'
}

export interface ReceptionDesksPage {
  items: ReceptionDesk[]
  total: number
}

export interface ReceptionDeskRepository {
  list(): Promise<ReceptionDesk[]>
  listPage(params: ListReceptionDesksPageParams): Promise<ReceptionDesksPage>
  create(input: ReceptionDeskInput): Promise<ReceptionDesk>
  update(id: string, input: ReceptionDeskInput): Promise<ReceptionDesk>
  remove(id: string): Promise<void>
}
