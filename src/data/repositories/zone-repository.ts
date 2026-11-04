import type { Zone, ZoneInput, ZoneListResponse, ZoneSortBy } from '../../domain/entities/zone-schema'

export interface ListZonesParams {
  page: number
  pageSize: number
  isActive?: boolean
  sortBy?: ZoneSortBy
  sortOrder?: 'asc' | 'desc'
  /** Sent as `X-Branch-ID` to narrow the list to one branch. */
  branchId?: string
}

export interface ZoneRepository {
  list(params: ListZonesParams): Promise<ZoneListResponse>
  get(id: string): Promise<Zone>
  create(input: ZoneInput): Promise<Zone>
  /** The branch cannot be changed, so it is not part of the update. */
  update(id: string, input: Omit<ZoneInput, 'branchId'>): Promise<Zone>
  remove(id: string): Promise<void>
  getCategoryZoneIds(categoryId: string): Promise<string[]>
  /** Replaces the category's whole default set. */
  setCategoryZoneIds(categoryId: string, zoneIds: string[]): Promise<string[]>
  getInvitationZoneIds(invitationId: string): Promise<string[]>
  /** Replaces the visit's whole set; an empty list clears it so category defaults apply. */
  setInvitationZoneIds(invitationId: string, zoneIds: string[]): Promise<string[]>
}
