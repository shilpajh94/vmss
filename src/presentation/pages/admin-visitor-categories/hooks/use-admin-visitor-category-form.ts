import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { VisitorCategoryInput } from '../../../../domain/entities/visitor-category-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

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

  const { getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, createVisitorCategoryUseCase, updateVisitorCategoryUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<VisitorCategoryInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof VisitorCategoryInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const user = await getCurrentStaffUserUseCase.execute()
      setCurrentUser(user)

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
  }, [getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, isEditMode, id, toast])

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

  const updateField = useCallback(<K extends keyof VisitorCategoryInput>(key: K, value: VisitorCategoryInput[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof VisitorCategoryInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Category name is required.'
    if (!values.code.trim()) nextErrors.code = 'Category code is required.'

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
        await createVisitorCategoryUseCase.execute(values)
        toast.success('Visitor category created.')
      }
      navigate('/admin/visitor-categories')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the visitor category. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createVisitorCategoryUseCase, updateVisitorCategoryUseCase, navigate, toast])

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
    updateField,
    submit,
    cancel,
  }
}
