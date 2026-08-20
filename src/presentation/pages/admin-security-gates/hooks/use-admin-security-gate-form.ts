import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building } from '../../../../domain/entities/building-schema'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { SecurityGateInput } from '../../../../domain/entities/security-gate-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const EMPTY_VALUES: SecurityGateInput = {
  name: '',
  buildingId: '',
  floorId: undefined,
  gateType: 'bidirectional',
  authMethod: undefined,
  connectivityStatus: 'online',
}

export function useAdminSecurityGateForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    getCurrentStaffUserUseCase,
    listBuildingsUseCase,
    listFloorsUseCase,
    listSecurityGatesUseCase,
    createSecurityGateUseCase,
    updateSecurityGateUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [floors, setFloors] = useState<Floor[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<SecurityGateInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof SecurityGateInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, buildingList, floorList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBuildingsUseCase.execute(),
        listFloorsUseCase.execute(),
      ])
      setCurrentUser(user)
      setBuildings(buildingList)
      setFloors(floorList)

      if (isEditMode) {
        const securityGates = await listSecurityGatesUseCase.execute()
        const securityGate = securityGates.find((candidate) => candidate.id === id)
        if (!securityGate) {
          setErrorMessage('That security gate could not be found.')
          return
        }
        setValues({
          name: securityGate.name,
          buildingId: securityGate.buildingId,
          floorId: securityGate.floorId,
          gateType: securityGate.gateType,
          authMethod: securityGate.authMethod,
          connectivityStatus: securityGate.connectivityStatus,
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
  }, [getCurrentStaffUserUseCase, listBuildingsUseCase, listFloorsUseCase, listSecurityGatesUseCase, isEditMode, id, toast])

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

  const updateField = useCallback(<K extends keyof SecurityGateInput>(key: K, value: SecurityGateInput[K]) => {
    setValues((current) => {
      if (key === 'buildingId' && current.buildingId !== value) {
        return { ...current, buildingId: value as SecurityGateInput['buildingId'], floorId: undefined }
      }
      return { ...current, [key]: value }
    })
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof SecurityGateInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Gate name/ID is required.'
    if (!values.buildingId.trim()) nextErrors.buildingId = 'Building is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateSecurityGateUseCase.execute(id, values)
        toast.success('Security gate updated.')
      } else {
        await createSecurityGateUseCase.execute(values)
        toast.success('Security gate created.')
      }
      navigate('/admin/security-gates')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the security gate. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createSecurityGateUseCase, updateSecurityGateUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/security-gates')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    buildings,
    floors: floorsForSelectedBuilding,
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
