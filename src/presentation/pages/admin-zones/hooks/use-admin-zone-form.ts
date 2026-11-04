import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { ApiError } from '../../../../data/api/api-error'
import type { ZoneInput } from '../../../../domain/entities/zone-schema'
import { useToast } from '../../../components/toast/toast-context'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useZoneFeature } from '../../../context/zone-feature-context'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { apiFieldErrors, toUserMessage } from '../../../utils/to-user-message'
import { loadZoneReferenceData, type ZoneReferenceData } from '../zone-reference-data'

const EMPTY_DETAILS: ZoneInput = { branchId: '', name: '', code: '', buildingId: null, floorId: null, gateIds: [], isActive: true }
const EMPTY_REFERENCES: ZoneReferenceData = { branches: [], buildings: [], floors: [], gates: [] }

type FieldErrors = Partial<Record<'branchId' | 'name' | 'code', string>>

export function useAdminZoneForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined
  const dependencies = useAppDependencies()
  const { getZoneUseCase, createZoneUseCase, updateZoneUseCase } = dependencies
  const toast = useToast()
  const { reportDisabled } = useZoneFeature()

  const [references, setReferences] = useState<ZoneReferenceData>(EMPTY_REFERENCES)
  const [details, setDetails] = useState<ZoneInput>(EMPTY_DETAILS)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)
    try {
      const [referenceData, zone] = await Promise.all([
        loadZoneReferenceData(dependencies, { activeOnly: !isEditMode }),
        isEditMode ? getZoneUseCase.execute(id) : Promise.resolve(undefined),
      ])
      setReferences(referenceData)
      setDetails(
        zone
          ? {
              branchId: zone.branchId,
              name: zone.name,
              code: zone.code,
              buildingId: zone.buildingId ?? null,
              floorId: zone.floorId ?? null,
              gateIds: zone.gateIds,
              isActive: zone.isActive,
            }
          : EMPTY_DETAILS,
      )
    } catch (error) {
      if (error instanceof ApiError && error.status === 404 && isEditMode) {
        setErrorMessage('That zone could not be found.')
      } else if (error instanceof ApiError && error.status === 404) {
        reportDisabled()
        setErrorMessage('Zone access control is not enabled for this environment.')
      } else {
        setErrorMessage('Something went wrong loading this page. Please try again.')
        toast.error('Something went wrong loading this page. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [dependencies, getZoneUseCase, isEditMode, id, toast, reportDisabled])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => void load(), [load])
  const { release } = useFormPageRefresh({ values: details, isLoading, reload: retry, baseline: isEditMode ? undefined : EMPTY_DETAILS })

  const updateField = useCallback(<K extends keyof ZoneInput>(key: K, value: ZoneInput[K]) => {
    setDetails((current) => ({ ...current, [key]: value }))
  }, [])

  // Choices narrow branch → building → floor, and gates follow the building (or the branch when none is chosen).
  const changeBranch = useCallback((branchId: string) => {
    setDetails((current) => ({ ...current, branchId, buildingId: null, floorId: null, gateIds: [] }))
  }, [])
  const changeBuilding = useCallback((buildingId: string) => {
    setDetails((current) => ({ ...current, buildingId: buildingId || null, floorId: null, gateIds: [] }))
  }, [])

  const buildingOptions = useMemo(
    () => references.buildings.filter((building) => building.branchId === details.branchId).map((building) => ({ value: building.id, label: building.name })),
    [references.buildings, details.branchId],
  )
  const floorOptions = useMemo(
    () => references.floors.filter((floor) => floor.buildingId === details.buildingId).map((floor) => ({ value: floor.id, label: floor.name })),
    [references.floors, details.buildingId],
  )
  const gateOptions = useMemo(
    () =>
      references.gates
        .filter((gate) => (details.buildingId ? gate.buildingId === details.buildingId : gate.branchId === details.branchId))
        .map((gate) => ({ value: gate.id, label: gate.name })),
    [references.gates, details.buildingId, details.branchId],
  )
  const toggleGate = useCallback((gateId: string, checked: boolean) => {
    setDetails((current) => ({
      ...current,
      gateIds: checked ? [...current.gateIds, gateId] : current.gateIds.filter((existing) => existing !== gateId),
    }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: FieldErrors = {}
    if (!details.branchId.trim()) nextErrors.branchId = 'Branch is required.'
    if (!details.name.trim()) nextErrors.name = 'Zone name is required.'
    if (!details.code.trim()) nextErrors.code = 'Zone code is required.'
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    const payload: ZoneInput = { ...details, name: details.name.trim(), code: details.code.trim() }
    setIsSaving(true)
    try {
      if (isEditMode) {
        const { branchId: _branchId, ...updatePayload } = payload
        await updateZoneUseCase.execute(id, updatePayload)
        toast.success('Zone updated.')
      } else {
        await createZoneUseCase.execute(payload)
        toast.success('Zone created.')
      }
      release()
      navigate('/admin/zones')
    } catch (error) {
      // The user stays on the form with what they typed; field messages show next to their controls.
      const fieldErrors = apiFieldErrors(error)
      setErrors({ name: fieldErrors.name, code: fieldErrors.code })
      toast.error(toUserMessage(error, `Something went wrong ${isEditMode ? 'updating' : 'creating'} the zone. Please try again.`))
    } finally {
      setIsSaving(false)
    }
  }, [details, isEditMode, id, createZoneUseCase, updateZoneUseCase, navigate, toast, release])

  const cancel = useCallback(() => navigate('/admin/zones'), [navigate])

  return {
    isEditMode,
    references,
    details,
    isLoading,
    errorMessage,
    retry,
    errors,
    isSaving,
    updateField,
    changeBranch,
    changeBuilding,
    toggleGate,
    buildingOptions,
    floorOptions,
    gateOptions,
    submit,
    cancel,
  }
}
