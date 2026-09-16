import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
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

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [badgeColorFilter, setBadgeColorFilter] = useState('')
  const [ndaRequirementFilter, setNdaRequirementFilter] = useState('')
  const [escortRequirementFilter, setEscortRequirementFilter] = useState('')

  const loadVisitorCategories = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listVisitorCategoriesUseCase.execute()])
        setCurrentUser(user)
        setVisitorCategories(list)
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the visitor categories. Please try again.')
        }
        toast.error('Something went wrong loading the visitor categories. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listVisitorCategoriesUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadVisitorCategories()
  }, [navigate, loadVisitorCategories])

  const retry = useCallback(() => {
    void loadVisitorCategories()
  }, [loadVisitorCategories])

  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadVisitorCategories({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  const filteredVisitorCategories = useMemo(() => {
    return visitorCategories.filter((category) => {
      if (badgeColorFilter && category.badgeColor !== badgeColorFilter) return false
      if (ndaRequirementFilter && category.ndaRequirement !== ndaRequirementFilter) return false
      if (escortRequirementFilter && category.escortRequirement !== escortRequirementFilter) return false
      return true
    })
  }, [visitorCategories, badgeColorFilter, ndaRequirementFilter, escortRequirementFilter])

  const isFiltering = badgeColorFilter !== '' || ndaRequirementFilter !== '' || escortRequirementFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => {
    setBadgeColorFilter('')
    setNdaRequirementFilter('')
    setEscortRequirementFilter('')
  }, [])

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
    visitorCategories: filteredVisitorCategories,
    hasAnyVisitorCategories: visitorCategories.length > 0,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    badgeColorFilter,
    setBadgeColorFilter,
    ndaRequirementFilter,
    setNdaRequirementFilter,
    escortRequirementFilter,
    setEscortRequirementFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
