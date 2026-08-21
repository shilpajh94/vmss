import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building } from '../../../../domain/entities/building-schema'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import type { ReceptionDeskInput } from '../../../../domain/entities/reception-desk-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const EMPTY_VALUES: ReceptionDeskInput = {
  name: '',
  buildingId: '',
  floorId: undefined,
  receptionistUserId: undefined,
  operatingHoursFrom: undefined,
  operatingHoursTo: undefined,
  status: 'active',
}

export function useAdminReceptionDeskForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    getCurrentStaffUserUseCase,
    listBuildingsUseCase,
    listFloorsUseCase,
    listHostEmployeesUseCase,
    listReceptionDesksUseCase,
    createReceptionDeskUseCase,
    updateReceptionDeskUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [floors, setFloors] = useState<Floor[]>([])
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<ReceptionDeskInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof ReceptionDeskInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, buildingList, floorList, hostEmployeeList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBuildingsUseCase.execute(),
        listFloorsUseCase.execute(),
        listHostEmployeesUseCase.execute(),
      ])
      setCurrentUser(user)
      setBuildings(buildingList)
      setFloors(floorList)
      setHostEmployees(hostEmployeeList)

      if (isEditMode) {
        const receptionDesks = await listReceptionDesksUseCase.execute()
        const receptionDesk = receptionDesks.find((candidate) => candidate.id === id)
        if (!receptionDesk) {
          setErrorMessage('That reception desk could not be found.')
          return
        }
        setValues({
          name: receptionDesk.name,
          buildingId: receptionDesk.buildingId,
          floorId: receptionDesk.floorId,
          receptionistUserId: receptionDesk.receptionistUserId,
          operatingHoursFrom: receptionDesk.operatingHoursFrom,
          operatingHoursTo: receptionDesk.operatingHoursTo,
          status: receptionDesk.status,
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
  }, [
    getCurrentStaffUserUseCase,
    listBuildingsUseCase,
    listFloorsUseCase,
    listHostEmployeesUseCase,
    listReceptionDesksUseCase,
    isEditMode,
    id,
    toast,
  ])

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

  const floorsForSelectedBuilding = useMemo(
    () => floors.filter((floor) => floor.buildingId === values.buildingId),
    [floors, values.buildingId],
  )

  const updateField = useCallback(<K extends keyof ReceptionDeskInput>(key: K, value: ReceptionDeskInput[K]) => {
    setValues((current) => {
      if (key === 'buildingId' && current.buildingId !== value) {
        return { ...current, buildingId: value as ReceptionDeskInput['buildingId'], floorId: undefined }
      }
      return { ...current, [key]: value }
    })
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof ReceptionDeskInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Desk name is required.'
    if (!values.buildingId.trim()) nextErrors.buildingId = 'Building is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateReceptionDeskUseCase.execute(id, values)
        toast.success('Reception desk updated.')
      } else {
        await createReceptionDeskUseCase.execute(values)
        toast.success('Reception desk created.')
      }
      navigate('/admin/reception-desks')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the reception desk. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createReceptionDeskUseCase, updateReceptionDeskUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/reception-desks')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    buildings,
    floors: floorsForSelectedBuilding,
    hostEmployees,
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
