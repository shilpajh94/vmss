import { useCallback, useMemo, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import { toUserMessage } from '../../../utils/to-user-message'

export interface FloorRow extends Floor {
  buildingName: string
}

const PAGE_SIZE = 20
const EMPTY_FLOORS: Floor[] = []
const EMPTY_BUILDINGS: Building[] = []
const EMPTY_DEPARTMENTS: Department[] = []

export function useAdminFloors() {
  const { listFloorsPageUseCase, listBuildingsUseCase, listDepartmentsUseCase, deleteFloorUseCase } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

  const [pendingDelete, setPendingDelete] = useState<FloorRow | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [accessLevelFilter, setAccessLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Polls skip while a delete dialog is open, so a background tick can't
  // replace data underneath it. Building and department names load once.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listFloorsPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        buildingId: buildingFilter || undefined,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
        accessLevel:
          accessLevelFilter === 'public' || accessLevelFilter === 'restricted' || accessLevelFilter === 'secure'
            ? accessLevelFilter
            : undefined,
      }),
    query: { page, buildingFilter, statusFilter, accessLevelFilter },
    reference: async () => {
      const [buildings, departments] = await Promise.all([listBuildingsUseCase.execute(), listDepartmentsUseCase.execute()])
      return { buildings, departments }
    },
    errorMessage: 'Something went wrong loading the floors. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const floorList = resource.data?.items ?? EMPTY_FLOORS
  const total = resource.data?.total ?? 0
  const buildings = resource.reference?.buildings ?? EMPTY_BUILDINGS
  const departments = resource.reference?.departments ?? EMPTY_DEPARTMENTS

  const buildingNameById = useMemo(() => new Map(buildings.map((building) => [building.id, building.name])), [buildings])

  const floors: FloorRow[] = useMemo(
    () => floorList.map((floor) => ({ ...floor, buildingName: buildingNameById.get(floor.buildingId) ?? '' })),
    [floorList, buildingNameById],
  )

  const departmentNamesByFloorId = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const department of departments) {
      if (!department.floorId) continue
      const names = map.get(department.floorId) ?? []
      names.push(department.name)
      map.set(department.floorId, names)
    }
    return map
  }, [departments])

  const buildingOptions = useMemo(
    () => buildings.map((building) => ({ value: building.id, label: building.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [buildings],
  )

  const isFiltering = buildingFilter !== '' || accessLevelFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeBuildingFilter = useCallback(
    (value: string) => {
      setBuildingFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeAccessLevelFilter = useCallback(
    (value: string) => {
      setAccessLevelFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setAccessLevelFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  const requestDelete = useCallback((floor: FloorRow) => setPendingDelete(floor), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteFloorUseCase.execute(pendingDelete.id)
      toast.success('Floor deleted.')
      setPendingDelete(undefined)
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the floor. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteFloorUseCase, toast, reload])

  return {
    currentUser,
    floors,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    departmentNamesByFloorId,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter: changeBuildingFilter,
    accessLevelFilter,
    setAccessLevelFilter: changeAccessLevelFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
