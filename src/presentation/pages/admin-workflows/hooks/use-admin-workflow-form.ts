import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'

interface WorkflowLevelForm {
  approverRoleId: string
}

const EMPTY_LEVEL: WorkflowLevelForm = { approverRoleId: '' }

export function useAdminWorkflowForm() {
  const navigate = useNavigate()
  const { visitorCategoryId } = useParams<{ visitorCategoryId: string }>()
  const isEditMode = visitorCategoryId !== undefined

  const { getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, listRolesUseCase, listApprovalWorkflowRulesUseCase, saveWorkflowUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [categoryOptions, setCategoryOptions] = useState<VisitorCategory[]>([])
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [selectedCategoryId, setSelectedCategoryId] = useState('')
  const [levels, setLevels] = useState<WorkflowLevelForm[]>([EMPTY_LEVEL])
  const [errors, setErrors] = useState<{ categoryId?: string; levels?: (string | undefined)[] }>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, categories, roleList, allRules] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listVisitorCategoriesUseCase.execute({ activeOnly: !isEditMode }),
        listRolesUseCase.execute(),
        listApprovalWorkflowRulesUseCase.execute(),
      ])
      setCurrentUser(user)
      setRoles(roleList)

      // Level 1 is always Reception's step (stepOrder 0) throughout the rest
      // of the app — the reception-only guard, "Approve & Delegate", and the
      // delegate-blocking rule all hardcode that position as meaning
      // Reception. Without this role, no workflow can be configured
      // correctly, so fail fast rather than let Level 1 end up unset.
      const receptionRole = roleList.find((role) => role.name.toLowerCase() === 'reception')
      if (!receptionRole) {
        setErrorMessage("A 'Reception' role must exist in Roles & Permissions before a workflow can be configured.")
        return
      }

      if (isEditMode) {
        setCategoryOptions(categories)
        setSelectedCategoryId(visitorCategoryId)

        // Mirrors `save-workflow.ts`'s defensive filter — a stale/soft-deleted
        // rule the backend didn't actually drop would otherwise pre-populate
        // the form with an extra level that was never really configured.
        const existingRules = allRules
          .filter((rule) => rule.visitorCategoryId === visitorCategoryId && rule.isActive)
          .sort((a, b) => a.stepOrder - b.stepOrder)

        const existingLevels =
          existingRules.length > 0 ? existingRules.map((rule) => ({ approverRoleId: rule.approverRoleId })) : [EMPTY_LEVEL]
        existingLevels[0] = { approverRoleId: receptionRole.id }
        setLevels(existingLevels)
      } else {
        const configuredCategoryIds = new Set(allRules.map((rule) => rule.visitorCategoryId))
        setCategoryOptions(categories.filter((category) => !configuredCategoryIds.has(category.id)))
        setSelectedCategoryId('')
        setLevels([{ approverRoleId: receptionRole.id }])
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [
    getCurrentStaffUserUseCase,
    listVisitorCategoriesUseCase,
    listRolesUseCase,
    listApprovalWorkflowRulesUseCase,
    isEditMode,
    visitorCategoryId,
    toast,
  ])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void load()
  }, [navigate, load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  useFormPageRefresh({ values: { selectedCategoryId, levels }, isLoading, reload: retry })

  const updateCategory = useCallback((categoryId: string) => {
    setSelectedCategoryId(categoryId)
  }, [])

  const addLevel = useCallback(() => {
    setLevels((current) => [...current, { ...EMPTY_LEVEL }])
  }, [])

  const removeLevel = useCallback((index: number) => {
    if (index === 0) return
    setLevels((current) => (current.length <= 1 ? current : current.filter((_, levelIndex) => levelIndex !== index)))
  }, [])

  const updateLevelApprover = useCallback((index: number, approverRoleId: string) => {
    // Level 1 is locked to the Reception role — its select is disabled in the
    // UI, but guard here too so the invariant holds regardless of caller.
    if (index === 0) return
    setLevels((current) => current.map((level, levelIndex) => (levelIndex === index ? { approverRoleId } : level)))
  }, [])

  const submit = useCallback(async () => {
    // A role assigned to an earlier level can't also approve a later one on
    // the same request — reproduced live: an "xss" category workflow had
    // Reception picked for both Level 1 and Level 2, so a request's Level 2
    // step ended up pending on Reception again instead of a distinct
    // approver, which is almost certainly a configuration mistake rather
    // than an intentional design.
    const levelErrors = levels.map((level, index) => {
      if (index === 0) return undefined
      if (!level.approverRoleId) return 'Approver is required.'
      const usedByEarlierLevel = levels.slice(0, index).some((earlierLevel) => earlierLevel.approverRoleId === level.approverRoleId)
      return usedByEarlierLevel ? 'This role is already assigned to an earlier level.' : undefined
    })
    const categoryError = selectedCategoryId ? undefined : 'Visitor category is required.'

    if (categoryError || levelErrors.some((error) => error !== undefined)) {
      setErrors({ categoryId: categoryError, levels: levelErrors })
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      await saveWorkflowUseCase.execute(selectedCategoryId, levels)
      toast.success(isEditMode ? 'Workflow updated.' : 'Workflow created.')
      navigate('/admin/workflows')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the workflow. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [levels, selectedCategoryId, isEditMode, saveWorkflowUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/workflows')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    categoryOptions,
    roles,
    isLoading,
    errorMessage,
    retry,
    selectedCategoryId,
    levels,
    errors,
    isSaving,
    updateCategory,
    addLevel,
    removeLevel,
    updateLevelApprover,
    submit,
    cancel,
  }
}
