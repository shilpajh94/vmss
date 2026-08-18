import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building, Floor } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export interface FloorRow extends Floor {
  buildingId: string
  buildingName: string
}

export function useAdminFloors() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listBuildingsUseCase, updateBuildingUseCase, listDepartmentsUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<FloorRow | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadFloors = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, buildingList, departmentList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBuildingsUseCase.execute(),
        listDepartmentsUseCase.execute(),
      ])
      setCurrentUser(user)
      setBuildings(buildingList)
      setDepartments(departmentList)
    } catch {
      setErrorMessage('Something went wrong loading the floors. Please try again.')
      toast.error('Something went wrong loading the floors. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBuildingsUseCase, listDepartmentsUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadFloors()
  }, [navigate, loadFloors])

  const retry = useCallback(() => {
    void loadFloors()
  }, [loadFloors])

  const floors: FloorRow[] = useMemo(
    () => buildings.flatMap((building) => building.floors.map((floor) => ({ ...floor, buildingId: building.id, buildingName: building.name }))),
    [buildings],
  )

  const departmentNameById = useMemo(() => new Map(departments.map((department) => [department.id, department.name])), [departments])

  const requestDelete = useCallback((floor: FloorRow) => setPendingDelete(floor), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      const building = buildings.find((candidate) => candidate.id === pendingDelete.buildingId)
      if (!building) throw new Error('Building not found')

      const nextFloors = building.floors.filter((floor) => floor.id !== pendingDelete.id)
      await updateBuildingUseCase.execute(building.id, {
        name: building.name,
        branchId: building.branchId,
        streetAddress: building.streetAddress,
        status: building.status,
        floors: nextFloors,
      })

      setBuildings((current) =>
        current.map((candidate) => (candidate.id === building.id ? { ...candidate, floors: nextFloors } : candidate)),
      )
      toast.success('Floor deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the floor. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, buildings, updateBuildingUseCase, toast])

  return {
    currentUser,
    floors,
    departmentNameById,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
