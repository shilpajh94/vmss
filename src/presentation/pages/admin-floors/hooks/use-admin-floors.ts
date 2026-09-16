import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export interface FloorRow extends Floor {
  buildingName: string
}

export function useAdminFloors() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listFloorsUseCase, listBuildingsUseCase, listDepartmentsUseCase, deleteFloorUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [floorList, setFloorList] = useState<Floor[]>([])
  const [buildings, setBuildings] = useState<Building[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<FloorRow | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [accessLevelFilter, setAccessLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const loadFloors = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, floorResult, buildingList, departmentList] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listFloorsUseCase.execute(),
          listBuildingsUseCase.execute(),
          listDepartmentsUseCase.execute(),
        ])
        setCurrentUser(user)
        setFloorList(floorResult)
        setBuildings(buildingList)
        setDepartments(departmentList)
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the floors. Please try again.')
        }
        toast.error('Something went wrong loading the floors. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listFloorsUseCase, listBuildingsUseCase, listDepartmentsUseCase, toast],
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
  usePolling(() => void loadFloors({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

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

  const filteredFloors = useMemo(() => {
    return floors.filter((floor) => {
      if (buildingFilter && floor.buildingId !== buildingFilter) return false
      if (accessLevelFilter && floor.accessLevel !== accessLevelFilter) return false
      if (statusFilter && (statusFilter === 'active') !== floor.isActive) return false
      return true
    })
  }, [floors, buildingFilter, accessLevelFilter, statusFilter])

  const isFiltering = buildingFilter !== '' || accessLevelFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setAccessLevelFilter('')
    setStatusFilter('')
  }, [])

  const requestDelete = useCallback((floor: FloorRow) => setPendingDelete(floor), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteFloorUseCase.execute(pendingDelete.id)
      setFloorList((current) => current.filter((floor) => floor.id !== pendingDelete.id))
      toast.success('Floor deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the floor. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteFloorUseCase, toast])

  return {
    currentUser,
    floors: filteredFloors,
    hasAnyFloors: floors.length > 0,
    departmentNamesByFloorId,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    accessLevelFilter,
    setAccessLevelFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
