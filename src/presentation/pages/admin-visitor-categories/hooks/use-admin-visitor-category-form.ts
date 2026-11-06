import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { fetchAllPages } from '../../../../data/api/fetch-all-pages'
import { ApiError } from '../../../../data/api/api-error'
import type { Zone } from '../../../../domain/entities/zone-schema'
import { useZoneFeature } from '../../../context/zone-feature-context'
import { PAGE_PERMISSIONS } from '../../../route-permissions'
import { usePermissions } from '../../../context/current-user-context'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import type { VisitorCategoryInput } from '../../../../domain/entities/visitor-category-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { toUserMessage } from '../../../utils/to-user-message'
import { wholeNumberRangeError } from '../../../utils/whole-number-range'

const EMPTY_VALUES: VisitorCategoryInput = {
  name: '',
  code: '',
  description: undefined,
  badgeColor: 'blue',
  ndaRequirement: undefined,
  escortRequirement: undefined,
  maxDurationMinutes: undefined,
}

export function useAdminVisitorCategoryForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    listVisitorCategoriesUseCase,
    createVisitorCategoryUseCase,
    updateVisitorCategoryUseCase,
    listRolesUseCase,
    saveWorkflowUseCase,
    listZonesUseCase,
    listBranchesUseCase,
    setCategoryZonesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<VisitorCategoryInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof VisitorCategoryInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  // Zones for a new category: a local draft saved after the category exists.
  const { enabled: zonesEnabled, reportDisabled } = useZoneFeature()
  const canManageZones = usePermissions().can(PAGE_PERMISSIONS.zonesManage)
  const showCreateZones = !isEditMode && zonesEnabled && canManageZones
  const [zones, setZones] = useState<Zone[]>([])
  const [branchNames, setBranchNames] = useState<Map<string, string>>(new Map())
  const [zoneDraft, setZoneDraft] = useState<string[]>([])
  const [zonePhase, setZonePhase] = useState<'loading' | 'ready' | 'error'>('loading')

  const loadZones = useCallback(async () => {
    setZonePhase('loading')
    try {
      const [zoneList, branches] = await Promise.all([
        fetchAllPages((page, pageSize) => listZonesUseCase.execute({ page, pageSize, isActive: true, sortBy: 'name', sortOrder: 'asc' }), { pageSize: 100 }),
        listBranchesUseCase.execute().catch(() => []),
      ])
      setZones(zoneList)
      setBranchNames(new Map(branches.map((branch) => [branch.id, branch.name])))
      setZonePhase('ready')
      // The branch default starts ticked. A failed lookup just leaves nothing ticked.
      try {
        const defaults = await listZonesUseCase.execute({ page: 1, pageSize: 1, isDefault: true, isActive: true })
        const defaultZone = defaults.data[0]
        if (defaultZone) setZoneDraft((current) => (current.includes(defaultZone.id) ? current : [...current, defaultZone.id]))
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) reportDisabled()
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) reportDisabled()
      setZonePhase('error')
    }
  }, [listZonesUseCase, listBranchesUseCase, reportDisabled])

  // Seeded once per mount of the form; unticking is never overwritten.
  useEffect(() => {
    if (showCreateZones) void loadZones()
  }, [showCreateZones, loadZones])

  const toggleZone = useCallback((zoneId: string, checked: boolean) => {
    setZoneDraft((current) => (checked ? [...current.filter((existing) => existing !== zoneId), zoneId] : current.filter((existing) => existing !== zoneId)))
  }, [])

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {

      if (isEditMode) {
        const visitorCategories = await listVisitorCategoriesUseCase.execute()
        const visitorCategory = visitorCategories.find((candidate) => candidate.id === id)
        if (!visitorCategory) {
          setErrorMessage('That visitor category could not be found.')
          return
        }
        setValues({
          name: visitorCategory.name,
          code: visitorCategory.code,
          description: visitorCategory.description,
          badgeColor: visitorCategory.badgeColor,
          ndaRequirement: visitorCategory.ndaRequirement,
          escortRequirement: visitorCategory.escortRequirement,
          maxDurationMinutes: visitorCategory.maxDurationMinutes,
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
  }, [listVisitorCategoriesUseCase, isEditMode, id, toast])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: values, isLoading, reload: retry })

  const updateField = useCallback(<K extends keyof VisitorCategoryInput>(key: K, value: VisitorCategoryInput[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof VisitorCategoryInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Category name is required.'
    if (!values.code.trim()) nextErrors.code = 'Category code is required.'
    const durationError = wholeNumberRangeError(values.maxDurationMinutes, { label: 'Max duration', min: 1 })
    if (durationError) nextErrors.maxDurationMinutes = durationError

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateVisitorCategoryUseCase.execute(id, values)
        toast.success('Visitor category updated.')
      } else {
        const created = await createVisitorCategoryUseCase.execute(values)
        toast.success('Visitor category created.')

        // The category now exists, so its zones can be saved (PUT replaces the whole set).
        // A failure keeps the category and sends the admin to Edit to retry.
        if (showCreateZones && zoneDraft.length > 0) {
          try {
            await setCategoryZonesUseCase.execute(created.id, zoneDraft)
          } catch (zoneError) {
            console.error('Failed to save the new category zones', zoneError)
            toast.error('Category created, but zones could not be saved. Set them from the Edit page.')
            release()
            navigate(`/admin/visitor-categories/${created.id}/edit`)
            return
          }
        }

        // Every category should have at least Reception approval by
        // default — additional levels are an opt-in the admin adds later via
        // /admin/workflows, but a category should never silently start with
        // zero approval levels. Best-effort: if this fails (e.g. no
        // "Reception" role exists yet), the category is still created; the
        // admin can configure its workflow manually from /admin/workflows.
        try {
          const roles = await listRolesUseCase.execute()
          const receptionRole = roles.find((role) => role.name.toLowerCase() === 'reception')
          if (receptionRole) {
            await saveWorkflowUseCase.execute(created.id, [{ approverRoleId: receptionRole.id }])
          }
        } catch (workflowError) {
          console.error('Failed to auto-configure the default Reception approval level', workflowError)
        }
      }
      release()
      navigate('/admin/visitor-categories')
    } catch (error) {
      toast.error(toUserMessage(error, `Something went wrong ${isEditMode ? 'updating' : 'creating'} the visitor category. Please try again.`))
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createVisitorCategoryUseCase, updateVisitorCategoryUseCase, listRolesUseCase, saveWorkflowUseCase, setCategoryZonesUseCase, showCreateZones, zoneDraft, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/visitor-categories')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    showCreateZones,
    zones,
    branchNames,
    zoneDraft,
    zonePhase,
    toggleZone,
    retryZones: loadZones,
    updateField,
    submit,
    cancel,
  }
}
