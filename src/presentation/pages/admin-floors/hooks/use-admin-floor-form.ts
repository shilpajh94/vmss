import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building } from '../../../../domain/entities/building-schema'
import type { FloorInput } from '../../../../domain/entities/floor-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { toUserMessage } from '../../../utils/to-user-message'
import { toFloorNumbers, validateFloorNumbers, type FloorNumberDrafts } from '../floor-form-validation'

type FloorFormValues = Omit<FloorInput, 'floorNumber' | 'capacity'> & FloorNumberDrafts
type FloorFormErrors = Partial<Record<'name' | 'buildingId' | 'floorNumber' | 'capacity', string>>

const EMPTY_VALUES: FloorFormValues = {
  buildingId: '',
  name: '',
  floorNumber: 0,
  capacity: 0,
  capacityType: 'guests',
  accessLevel: 'public',
  isActive: true,
}

export function useAdminFloorForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const { getCurrentStaffUserUseCase, listBuildingsUseCase, listFloorsUseCase, createFloorUseCase, updateFloorUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<FloorFormValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<FloorFormErrors>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, buildingList] = await Promise.all([getCurrentStaffUserUseCase.execute(), listBuildingsUseCase.execute({ activeOnly: !isEditMode })])
      setCurrentUser(user)
      setBuildings(buildingList)

      if (isEditMode) {
        const floors = await listFloorsUseCase.execute()
        const floor = floors.find((candidate) => candidate.id === id)
        if (!floor) {
          setErrorMessage('That floor could not be found.')
          return
        }
        setValues({
          buildingId: floor.buildingId,
          name: floor.name,
          floorNumber: floor.floorNumber,
          capacity: floor.capacity,
          capacityType: floor.capacityType,
          accessLevel: floor.accessLevel,
          isActive: floor.isActive,
        })
      } else {
        setValues(EMPTY_VALUES)
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBuildingsUseCase, listFloorsUseCase, isEditMode, id, toast])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: values, isLoading, reload: retry })

  const updateField = useCallback(<K extends keyof FloorFormValues>(key: K, value: FloorFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: FloorFormErrors = validateFloorNumbers(values)
    if (!values.name.trim()) nextErrors.name = 'Floor name is required.'
    if (!values.buildingId.trim()) nextErrors.buildingId = 'Building is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    const input: FloorInput = { ...values, ...toFloorNumbers(values) }
    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateFloorUseCase.execute(id, input)
        toast.success('Floor updated.')
      } else {
        await createFloorUseCase.execute(input)
        toast.success('Floor created.')
      }
      release()
      navigate('/admin/floors')
    } catch (error) {
      toast.error(toUserMessage(error, `Something went wrong ${isEditMode ? 'updating' : 'creating'} the floor. Please try again.`))
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createFloorUseCase, updateFloorUseCase, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/floors')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    buildings,
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
