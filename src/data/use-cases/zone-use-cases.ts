import type { Zone, ZoneInput, ZoneListResponse } from '../../domain/entities/zone-schema'
import type { ListZonesParams, ZoneRepository } from '../repositories/zone-repository'

export class ListZonesUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(params: ListZonesParams): Promise<ZoneListResponse> {
    return this.zoneRepository.list(params)
  }
}

export class GetZoneUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(id: string): Promise<Zone> {
    return this.zoneRepository.get(id)
  }
}

export class CreateZoneUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(input: ZoneInput): Promise<Zone> {
    return this.zoneRepository.create(input)
  }
}

export class UpdateZoneUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(id: string, input: Omit<ZoneInput, 'branchId'>): Promise<Zone> {
    return this.zoneRepository.update(id, input)
  }
}

export class DeleteZoneUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(id: string): Promise<void> {
    return this.zoneRepository.remove(id)
  }
}

export class GetCategoryZonesUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(categoryId: string): Promise<string[]> {
    return this.zoneRepository.getCategoryZoneIds(categoryId)
  }
}

export class SetCategoryZonesUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(categoryId: string, zoneIds: string[]): Promise<string[]> {
    return this.zoneRepository.setCategoryZoneIds(categoryId, zoneIds)
  }
}

export class GetInvitationZonesUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(invitationId: string): Promise<string[]> {
    return this.zoneRepository.getInvitationZoneIds(invitationId)
  }
}

export class SetInvitationZonesUseCase {
  private readonly zoneRepository: ZoneRepository

  constructor(zoneRepository: ZoneRepository) {
    this.zoneRepository = zoneRepository
  }

  execute(invitationId: string, zoneIds: string[]): Promise<string[]> {
    return this.zoneRepository.setInvitationZoneIds(invitationId, zoneIds)
  }
}
