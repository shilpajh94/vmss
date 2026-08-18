import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { BuildingInput, Checkpoint, Floor } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export type FloorDetailsInput = Omit<Floor, 'id' | 'checkpoints'>

type BuildingDetails = Omit<BuildingInput, 'floors'>

const EMPTY_DETAILS: BuildingDetails = {
  name: '',
  branchId: '',
  streetAddress: undefined,
  status: 'active',
}

type FloorModalState = { mode: 'add' } | { mode: 'edit'; floor: Floor } | undefined
type CheckpointModalState = { floorId: string; mode: 'add' } | { floorId: string; mode: 'edit'; checkpoint: Checkpoint } | undefined

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
    listDepartmentsUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [details, setDetails] = useState<BuildingDetails>(EMPTY_DETAILS)
  const [floors, setFloors] = useState<Floor[]>([])
  const [expandedFloorIds, setExpandedFloorIds] = useState<Set<string>>(new Set())
  const [errors, setErrors] = useState<Partial<Record<keyof BuildingDetails, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const [floorModal, setFloorModal] = useState<FloorModalState>(undefined)
  const [pendingDeleteFloor, setPendingDeleteFloor] = useState<Floor | undefined>(undefined)

  const [checkpointModal, setCheckpointModal] = useState<CheckpointModalState>(undefined)
  const [pendingDeleteCheckpoint, setPendingDeleteCheckpoint] = useState<{ floorId: string; checkpoint: Checkpoint } | undefined>(
    undefined,
  )

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, branchList, departmentList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBranchesUseCase.execute(),
        listDepartmentsUseCase.execute(),
      ])
      setCurrentUser(user)
      setBranches(branchList)
      setDepartments(departmentList)

      if (isEditMode) {
        const buildings = await listBuildingsUseCase.execute()
        const building = buildings.find((candidate) => candidate.id === id)
        if (!building) {
          setErrorMessage('That building could not be found.')
          return
        }
        setDetails({
          name: building.name,
          branchId: building.branchId,
          streetAddress: building.streetAddress,
          status: building.status,
        })
        setFloors(building.floors)
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
  }, [getCurrentStaffUserUseCase, listBranchesUseCase, listDepartmentsUseCase, listBuildingsUseCase, isEditMode, id, toast])

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

  const updateField = useCallback(<K extends keyof BuildingDetails>(key: K, value: BuildingDetails[K]) => {
    setDetails((current) => ({ ...current, [key]: value }))
  }, [])

  // Floors

  const openAddFloorModal = useCallback(() => setFloorModal({ mode: 'add' }), [])
  const openEditFloorModal = useCallback((floor: Floor) => setFloorModal({ mode: 'edit', floor }), [])
  const closeFloorModal = useCallback(() => setFloorModal(undefined), [])

  const saveFloor = useCallback(
    (details: FloorDetailsInput) => {
      if (!floorModal) return

      if (floorModal.mode === 'add') {
        const newFloor: Floor = { id: crypto.randomUUID(), checkpoints: [], ...details }
        setFloors((current) => [...current, newFloor])
      } else {
        const floorId = floorModal.floor.id
        setFloors((current) => current.map((floor) => (floor.id === floorId ? { ...floor, ...details } : floor)))
      }
      setFloorModal(undefined)
    },
    [floorModal],
  )

  const requestDeleteFloor = useCallback((floor: Floor) => setPendingDeleteFloor(floor), [])
  const cancelDeleteFloor = useCallback(() => setPendingDeleteFloor(undefined), [])

  const confirmDeleteFloor = useCallback(() => {
    if (!pendingDeleteFloor) return
    const floorId = pendingDeleteFloor.id
    setFloors((current) => current.filter((floor) => floor.id !== floorId))
    setExpandedFloorIds((current) => {
      const next = new Set(current)
      next.delete(floorId)
      return next
    })
    setPendingDeleteFloor(undefined)
  }, [pendingDeleteFloor])

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

  // Checkpoints

  const openAddCheckpointModal = useCallback((floorId: string) => setCheckpointModal({ floorId, mode: 'add' }), [])
  const openEditCheckpointModal = useCallback(
    (floorId: string, checkpoint: Checkpoint) => setCheckpointModal({ floorId, mode: 'edit', checkpoint }),
    [],
  )
  const closeCheckpointModal = useCallback(() => setCheckpointModal(undefined), [])

  const saveCheckpoint = useCallback(
    (name: string) => {
      if (!checkpointModal) return
      const { floorId } = checkpointModal

      setFloors((current) =>
        current.map((floor) => {
          if (floor.id !== floorId) return floor

          if (checkpointModal.mode === 'add') {
            const newCheckpoint: Checkpoint = { id: crypto.randomUUID(), name }
            return { ...floor, checkpoints: [...floor.checkpoints, newCheckpoint] }
          }

          const checkpointId = checkpointModal.checkpoint.id
          return {
            ...floor,
            checkpoints: floor.checkpoints.map((checkpoint) => (checkpoint.id === checkpointId ? { ...checkpoint, name } : checkpoint)),
          }
        }),
      )
      setCheckpointModal(undefined)
    },
    [checkpointModal],
  )

  const requestDeleteCheckpoint = useCallback(
    (floorId: string, checkpoint: Checkpoint) => setPendingDeleteCheckpoint({ floorId, checkpoint }),
    [],
  )
  const cancelDeleteCheckpoint = useCallback(() => setPendingDeleteCheckpoint(undefined), [])

  const confirmDeleteCheckpoint = useCallback(() => {
    if (!pendingDeleteCheckpoint) return
    const { floorId, checkpoint } = pendingDeleteCheckpoint

    setFloors((current) =>
      current.map((floor) =>
        floor.id === floorId ? { ...floor, checkpoints: floor.checkpoints.filter((c) => c.id !== checkpoint.id) } : floor,
      ),
    )
    setPendingDeleteCheckpoint(undefined)
  }, [pendingDeleteCheckpoint])

  // Submit

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof BuildingDetails, string>> = {}
    if (!details.name.trim()) nextErrors.name = 'Building name is required.'
    if (!details.branchId.trim()) nextErrors.branchId = 'Branch is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    const input: BuildingInput = { ...details, floors }

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateBuildingUseCase.execute(id, input)
        toast.success('Building updated.')
      } else {
        await createBuildingUseCase.execute(input)
        toast.success('Building created.')
      }
      navigate('/admin/buildings')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the building. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [details, floors, isEditMode, id, createBuildingUseCase, updateBuildingUseCase, navigate, toast])

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
    toggleFloorExpanded,
    openAddCheckpointModal,
    openEditCheckpointModal,
    closeCheckpointModal,
    checkpointModal,
    saveCheckpoint,
    requestDeleteCheckpoint,
    cancelDeleteCheckpoint,
    confirmDeleteCheckpoint,
    pendingDeleteCheckpoint,
    submit,
    cancel,
  }
}
