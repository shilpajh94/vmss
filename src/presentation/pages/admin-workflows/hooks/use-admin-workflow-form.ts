import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'

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
        listVisitorCategoriesUseCase.execute(),
        listRolesUseCase.execute(),
        listApprovalWorkflowRulesUseCase.execute(),
      ])
      setCurrentUser(user)
      setRoles(roleList)

      if (isEditMode) {
        setCategoryOptions(categories)
        setSelectedCategoryId(visitorCategoryId)

        const existingRules = allRules
          .filter((rule) => rule.visitorCategoryId === visitorCategoryId)
          .sort((a, b) => a.stepOrder - b.stepOrder)

        setLevels(existingRules.length > 0 ? existingRules.map((rule) => ({ approverRoleId: rule.approverRoleId })) : [EMPTY_LEVEL])
      } else {
        const configuredCategoryIds = new Set(allRules.map((rule) => rule.visitorCategoryId))
        setCategoryOptions(categories.filter((category) => !configuredCategoryIds.has(category.id)))
        setSelectedCategoryId('')
        setLevels([EMPTY_LEVEL])
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

  const updateCategory = useCallback((categoryId: string) => {
    setSelectedCategoryId(categoryId)
  }, [])

  const addLevel = useCallback(() => {
    setLevels((current) => [...current, { ...EMPTY_LEVEL }])
  }, [])

  const removeLevel = useCallback((index: number) => {
    setLevels((current) => (current.length <= 1 ? current : current.filter((_, levelIndex) => levelIndex !== index)))
  }, [])

  const updateLevelApprover = useCallback((index: number, approverRoleId: string) => {
    setLevels((current) => current.map((level, levelIndex) => (levelIndex === index ? { approverRoleId } : level)))
  }, [])

  const submit = useCallback(async () => {
    const levelErrors = levels.map((level) => (level.approverRoleId ? undefined : 'Approver is required.'))
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
