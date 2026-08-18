import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building, Floor } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

type FloorFormValues = Omit<Floor, 'id' | 'checkpoints'> & { buildingId: string }

const EMPTY_VALUES: FloorFormValues = {
  name: '',
  buildingId: '',
  capacityCount: 0,
  capacityUnit: 'Guests',
  accessLevel: 'public',
  departmentIds: [],
  status: 'active',
}

export function useAdminFloorForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const { getCurrentStaffUserUseCase, listBuildingsUseCase, listDepartmentsUseCase, updateBuildingUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<FloorFormValues>(EMPTY_VALUES)
  const [originalBuildingId, setOriginalBuildingId] = useState<string | undefined>(undefined)
  const [errors, setErrors] = useState<Partial<Record<'name' | 'buildingId', string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
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

      if (isEditMode) {
        const building = buildingList.find((candidate) => candidate.floors.some((floor) => floor.id === id))
        const floor = building?.floors.find((candidate) => candidate.id === id)
        if (!building || !floor) {
          setErrorMessage('That floor could not be found.')
          return
        }
        setValues({
          name: floor.name,
          buildingId: building.id,
          capacityCount: floor.capacityCount,
          capacityUnit: floor.capacityUnit,
          accessLevel: floor.accessLevel,
          departmentIds: floor.departmentIds,
          status: floor.status,
        })
        setOriginalBuildingId(building.id)
      } else {
        setValues(EMPTY_VALUES)
        setOriginalBuildingId(undefined)
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBuildingsUseCase, listDepartmentsUseCase, isEditMode, id, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void load()
  }, [navigate, load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const updateField = useCallback(<K extends keyof FloorFormValues>(key: K, value: FloorFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<'name' | 'buildingId', string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Floor name is required.'
    if (!values.buildingId.trim()) nextErrors.buildingId = 'Building is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    const floorDetails: Omit<Floor, 'id' | 'checkpoints'> = {
      name: values.name,
      capacityCount: values.capacityCount,
      capacityUnit: values.capacityUnit,
      accessLevel: values.accessLevel,
      departmentIds: values.departmentIds,
      status: values.status,
    }

    setIsSaving(true)
    try {
      if (isEditMode && originalBuildingId) {
        const originalBuilding = buildings.find((candidate) => candidate.id === originalBuildingId)
        if (!originalBuilding) throw new Error('Original building not found')
        const existingFloor = originalBuilding.floors.find((floor) => floor.id === id)
        if (!existingFloor) throw new Error('Floor not found')

        if (values.buildingId === originalBuildingId) {
          const nextFloors = originalBuilding.floors.map((floor) => (floor.id === id ? { ...floor, ...floorDetails } : floor))
          await updateBuildingUseCase.execute(originalBuilding.id, {
            name: originalBuilding.name,
            branchId: originalBuilding.branchId,
            streetAddress: originalBuilding.streetAddress,
            status: originalBuilding.status,
            floors: nextFloors,
          })
        } else {
          const newBuilding = buildings.find((candidate) => candidate.id === values.buildingId)
          if (!newBuilding) throw new Error('Target building not found')

          const remainingFloors = originalBuilding.floors.filter((floor) => floor.id !== id)
          await updateBuildingUseCase.execute(originalBuilding.id, {
            name: originalBuilding.name,
            branchId: originalBuilding.branchId,
            streetAddress: originalBuilding.streetAddress,
            status: originalBuilding.status,
            floors: remainingFloors,
          })

          const movedFloor: Floor = { ...existingFloor, ...floorDetails }
          await updateBuildingUseCase.execute(newBuilding.id, {
            name: newBuilding.name,
            branchId: newBuilding.branchId,
            streetAddress: newBuilding.streetAddress,
            status: newBuilding.status,
            floors: [...newBuilding.floors, movedFloor],
          })
        }
        toast.success('Floor updated.')
      } else {
        const targetBuilding = buildings.find((candidate) => candidate.id === values.buildingId)
        if (!targetBuilding) throw new Error('Building not found')

        const newFloor: Floor = { id: crypto.randomUUID(), checkpoints: [], ...floorDetails }
        await updateBuildingUseCase.execute(targetBuilding.id, {
          name: targetBuilding.name,
          branchId: targetBuilding.branchId,
          streetAddress: targetBuilding.streetAddress,
          status: targetBuilding.status,
          floors: [...targetBuilding.floors, newFloor],
        })
        toast.success('Floor created.')
      }
      navigate('/admin/floors')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the floor. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, originalBuildingId, buildings, id, updateBuildingUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/floors')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    buildings,
    departments,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  }
}
