import type { Kiosk, KioskInput } from '../../domain/entities/kiosk-schema'

export interface ListKiosksPageParams {
  page: number
  pageSize: number
  status?: 'active' | 'inactive'
  includeHidden: boolean
  sortBy: 'name' | 'created_at'
  sortOrder: 'asc' | 'desc'
}

export interface KiosksPage {
  items: Kiosk[]
  total: number
}

export interface KioskRepository {
  listPage(params: ListKiosksPageParams): Promise<KiosksPage>
  get(id: string): Promise<Kiosk>
  create(input: KioskInput): Promise<Kiosk>
  update(id: string, input: Partial<KioskInput>): Promise<Kiosk>
  setHidden(id: string, isHidden: boolean): Promise<Kiosk>
  remove(id: string): Promise<void>
}
