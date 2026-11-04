import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { Floor } from '../../../domain/entities/floor-schema'
import type { Device } from '../../../domain/entities/managed-device-schema'
import type { AppDependencies } from '../../../composition-root'

/** Names behind a zone's branch / building / floor / gate ids. A gate is a registered device in `security` mode. */
export interface ZoneReferenceData {
  branches: Branch[]
  buildings: Building[]
  floors: Floor[]
  gates: Device[]
}

type ReferenceDependencies = Pick<AppDependencies, 'listBranchesUseCase' | 'listBuildingsUseCase' | 'listFloorsUseCase' | 'listDevicesPageUseCase'>

export async function loadZoneReferenceData(
  { listBranchesUseCase, listBuildingsUseCase, listFloorsUseCase, listDevicesPageUseCase }: ReferenceDependencies,
  options: { activeOnly?: boolean } = {},
): Promise<ZoneReferenceData> {
  const [branches, buildings, floors, gatePage] = await Promise.all([
    listBranchesUseCase.execute({ activeOnly: options.activeOnly }),
    listBuildingsUseCase.execute(),
    listFloorsUseCase.execute(),
    listDevicesPageUseCase.execute({ operatingMode: 'security', page: 1, pageSize: 100, sortBy: 'name', sortOrder: 'asc' }),
  ])
  return { branches, buildings, floors, gates: gatePage.items }
}
