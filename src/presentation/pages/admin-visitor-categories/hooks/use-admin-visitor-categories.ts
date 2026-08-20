import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminVisitorCategories() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, deleteVisitorCategoryUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<VisitorCategory | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadVisitorCategories = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listVisitorCategoriesUseCase.execute()])
      setCurrentUser(user)
      setVisitorCategories(list)
    } catch {
      setErrorMessage('Something went wrong loading the visitor categories. Please try again.')
      toast.error('Something went wrong loading the visitor categories. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadVisitorCategories()
  }, [navigate, loadVisitorCategories])

  const retry = useCallback(() => {
    void loadVisitorCategories()
  }, [loadVisitorCategories])

  const requestDelete = useCallback((visitorCategory: VisitorCategory) => {
    setPendingDelete(visitorCategory)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteVisitorCategoryUseCase.execute(pendingDelete.id)
      setVisitorCategories((current) => current.filter((visitorCategory) => visitorCategory.id !== pendingDelete.id))
      toast.success('Visitor category deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the visitor category. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteVisitorCategoryUseCase, toast])

  return {
    currentUser,
    visitorCategories,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
