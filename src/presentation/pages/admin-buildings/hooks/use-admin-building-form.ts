import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { BuildingInput } from '../../../../domain/entities/building-schema'
import type { Floor, FloorInput } from '../../../../domain/entities/floor-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { toUserMessage } from '../../../utils/to-user-message'

export type FloorDetailsInput = Omit<FloorInput, 'buildingId'>

const EMPTY_DETAILS: BuildingInput = {
  name: '',
  branchId: '',
  code: '',
  address: '',
  isActive: true,
}

type FloorModalState = { mode: 'add' } | { mode: 'edit'; floor: Floor } | undefined

export function useAdminBuildingForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    getCurrentStaffUserUseCase,
    listBranchesUseCase,
    listBuildingsUseCase,
    createBuildingUseCase,
    updateBuildingUseCase,
    listFloorsUseCase,
    createFloorUseCase,
    updateFloorUseCase,
    deleteFloorUseCase,
    listDepartmentsUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [details, setDetails] = useState<BuildingInput>(EMPTY_DETAILS)
  const [floors, setFloors] = useState<Floor[]>([])
  const [expandedFloorIds, setExpandedFloorIds] = useState<Set<string>>(new Set())
  const [errors, setErrors] = useState<Partial<Record<keyof BuildingInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingFloor, setIsSavingFloor] = useState(false)

  const [floorModal, setFloorModal] = useState<FloorModalState>(undefined)
  const [pendingDeleteFloor, setPendingDeleteFloor] = useState<Floor | undefined>(undefined)
  const [isDeletingFloor, setIsDeletingFloor] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, branchList, departmentList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBranchesUseCase.execute({ activeOnly: !isEditMode }),
        listDepartmentsUseCase.execute(),
      ])
      setCurrentUser(user)
      setBranches(branchList)
      setDepartments(departmentList)

      if (isEditMode) {
        const [buildings, buildingFloors] = await Promise.all([listBuildingsUseCase.execute(), listFloorsUseCase.execute(id)])
        const building = buildings.find((candidate) => candidate.id === id)
        if (!building) {
          setErrorMessage('That building could not be found.')
          toast.error('That building could not be found.')
          return
        }
        setDetails({
          name: building.name,
          branchId: building.branchId,
          code: building.code,
          address: building.address,
          isActive: building.isActive,
        })
        setFloors(buildingFloors)
      } else {
        setDetails(EMPTY_DETAILS)
        setFloors([])
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [
    getCurrentStaffUserUseCase,
    listBranchesUseCase,
    listBuildingsUseCase,
    listDepartmentsUseCase,
    listFloorsUseCase,
    isEditMode,
    id,
    toast,
  ])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: details, isLoading, reload: retry })

  const updateField = useCallback(<K extends keyof BuildingInput>(key: K, value: BuildingInput[K]) => {
    setDetails((current) => ({ ...current, [key]: value }))
  }, [])

  // Floors — each floor operation round-trips through the real /floors endpoints immediately,
  // since floors are their own backend resource (not part of the building's create/update payload).

  const openAddFloorModal = useCallback(() => setFloorModal({ mode: 'add' }), [])
  const openEditFloorModal = useCallback((floor: Floor) => setFloorModal({ mode: 'edit', floor }), [])
  const closeFloorModal = useCallback(() => setFloorModal(undefined), [])

  const saveFloor = useCallback(
    async (floorDetails: FloorDetailsInput) => {
      if (!floorModal || !id) return

      setIsSavingFloor(true)
      try {
        if (floorModal.mode === 'add') {
          const created = await createFloorUseCase.execute({ buildingId: id, ...floorDetails })
          setFloors((current) => [...current, created])
          toast.success('Floor added.')
        } else {
          const updated = await updateFloorUseCase.execute(floorModal.floor.id, { buildingId: id, ...floorDetails })
          setFloors((current) => current.map((floor) => (floor.id === updated.id ? updated : floor)))
          toast.success('Floor updated.')
        }
        setFloorModal(undefined)
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong saving the floor. Please try again.'))
      } finally {
        setIsSavingFloor(false)
      }
    },
    [floorModal, id, createFloorUseCase, updateFloorUseCase, toast],
  )

  const requestDeleteFloor = useCallback((floor: Floor) => setPendingDeleteFloor(floor), [])
  const cancelDeleteFloor = useCallback(() => setPendingDeleteFloor(undefined), [])

  const confirmDeleteFloor = useCallback(async () => {
    if (!pendingDeleteFloor) return

    setIsDeletingFloor(true)
    try {
      await deleteFloorUseCase.execute(pendingDeleteFloor.id)
      const floorId = pendingDeleteFloor.id
      setFloors((current) => current.filter((floor) => floor.id !== floorId))
      setExpandedFloorIds((current) => {
        const next = new Set(current)
        next.delete(floorId)
        return next
      })
      toast.success('Floor deleted.')
      setPendingDeleteFloor(undefined)
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the floor. Please try again.'))
    } finally {
      setIsDeletingFloor(false)
    }
  }, [pendingDeleteFloor, deleteFloorUseCase, toast])

  const toggleFloorExpanded = useCallback((floorId: string) => {
    setExpandedFloorIds((current) => {
      const next = new Set(current)
      if (next.has(floorId)) {
        next.delete(floorId)
      } else {
        next.add(floorId)
      }
      return next
    })
  }, [])

  // Submit — building details only; floors are saved independently above.

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof BuildingInput, string>> = {}
    if (!details.name.trim()) nextErrors.name = 'Building name is required.'
    if (!details.branchId.trim()) nextErrors.branchId = 'Branch is required.'
    if (!details.code.trim()) nextErrors.code = 'Building code is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateBuildingUseCase.execute(id, details)
        toast.success('Building updated.')
        release()
        navigate('/admin/buildings')
      } else {
        const created = await createBuildingUseCase.execute(details)
        toast.success('Building created.')
        release()
        navigate(`/admin/buildings/${created.id}/edit`)
      }
    } catch (error) {
      toast.error(toUserMessage(error, `Something went wrong ${isEditMode ? 'updating' : 'creating'} the building. Please try again.`))
    } finally {
      setIsSaving(false)
    }
  }, [details, isEditMode, id, createBuildingUseCase, updateBuildingUseCase, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/buildings')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    branches,
    departments,
    isLoading,
    errorMessage,
    retry,
    details,
    floors,
    expandedFloorIds,
    errors,
    isSaving,
    isSavingFloor,
    updateField,
    openAddFloorModal,
    openEditFloorModal,
    closeFloorModal,
    floorModal,
    saveFloor,
    requestDeleteFloor,
    cancelDeleteFloor,
    confirmDeleteFloor,
    pendingDeleteFloor,
    isDeletingFloor,
    toggleFloorExpanded,
    submit,
    cancel,
  }
}
