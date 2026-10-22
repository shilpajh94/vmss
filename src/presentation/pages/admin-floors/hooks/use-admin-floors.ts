import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export interface FloorRow extends Floor {
  buildingName: string
}

const PAGE_SIZE = 20

export function useAdminFloors() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listFloorsPageUseCase, listBuildingsUseCase, listDepartmentsUseCase, deleteFloorUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [floorList, setFloorList] = useState<Floor[]>([])
  const [total, setTotal] = useState(0)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()

  const [pendingDelete, setPendingDelete] = useState<FloorRow | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [accessLevelFilter, setAccessLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/page/retry/refresh/post-mutation - keeps the
  // current rows on screen with a progress cue. `background`: the 15s poll.
  const loadFloors = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, floorResult, buildingList, departmentList] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
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
          listBuildingsUseCase.execute(),
          listDepartmentsUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setFloorList(floorResult.items)
        setTotal(floorResult.total)
        setBuildings(buildingList)
        setDepartments(departmentList)
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the floors. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listFloorsPageUseCase, listBuildingsUseCase, listDepartmentsUseCase, page, buildingFilter, statusFilter, accessLevelFilter, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadFloors()
  }, [navigate, loadFloors])

  const retry = useCallback(() => {
    void loadFloors()
  }, [loadFloors])

  // Auto-refreshes the inventory every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadFloors('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

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
      await loadFloors()
    } catch {
      toast.error('Something went wrong deleting the floor. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteFloorUseCase, toast, loadFloors])

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
