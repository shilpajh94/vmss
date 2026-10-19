import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { VisitorCategoryBulkCreateOut } from '../../../../domain/entities/visitor-category-out-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20

export function useAdminVisitorCategories() {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listVisitorCategoriesPageUseCase,
    deleteVisitorCategoryUseCase,
    bulkCreateVisitorCategoriesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[]>([])
  const [total, setTotal] = useState(0)
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<VisitorCategory | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isBulkAddOpen, setIsBulkAddOpen] = useState(false)
  const [isBulkCreating, setIsBulkCreating] = useState(false)
  const [bulkCreateResult, setBulkCreateResult] = useState<VisitorCategoryBulkCreateOut | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [badgeColorFilter, setBadgeColorFilter] = useState('')
  const [ndaRequirementFilter, setNdaRequirementFilter] = useState('')
  const [escortRequirementFilter, setEscortRequirementFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/page/retry/refresh/post-mutation - keeps the
  // current rows on screen with a progress cue. `background`: the 15s poll.
  const loadVisitorCategories = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listVisitorCategoriesPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            badgeColor: badgeColorFilter || undefined,
            ndaRequirement: ndaRequirementFilter || undefined,
            escortRequirement: escortRequirementFilter || undefined,
          }),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setVisitorCategories(page_.items)
        setTotal(page_.total)
        setLastUpdatedAt(new Date())
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the visitor categories. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listVisitorCategoriesPageUseCase, page, badgeColorFilter, ndaRequirementFilter, escortRequirementFilter, toast],
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

  const isActionInProgress = pendingDelete !== undefined || isDeleting || isBulkAddOpen
  usePolling(() => void loadVisitorCategories('background'), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing, lastUpdatedAt })

  const isFiltering = badgeColorFilter !== '' || ndaRequirementFilter !== '' || escortRequirementFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeBadgeColorFilter = useCallback(
    (value: string) => {
      setBadgeColorFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeNdaRequirementFilter = useCallback(
    (value: string) => {
      setNdaRequirementFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeEscortRequirementFilter = useCallback(
    (value: string) => {
      setEscortRequirementFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setBadgeColorFilter('')
    setNdaRequirementFilter('')
    setEscortRequirementFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

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
      toast.success('Visitor category deleted.')
      setPendingDelete(undefined)
      await loadVisitorCategories()
    } catch {
      toast.error('Something went wrong deleting the visitor category. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteVisitorCategoryUseCase, toast, loadVisitorCategories])

  const openBulkAdd = useCallback(() => {
    setBulkCreateResult(undefined)
    setIsBulkAddOpen(true)
  }, [])

  const closeBulkAdd = useCallback(() => {
    setIsBulkAddOpen(false)
    setBulkCreateResult(undefined)
  }, [])

  const submitBulkAdd = useCallback(
    async (names: string[]) => {
      setIsBulkCreating(true)
      try {
        const result = await bulkCreateVisitorCategoriesUseCase.execute({ names })
        setBulkCreateResult(result)
        if (result.createdCount > 0) {
          await loadVisitorCategories()
        }
      } catch {
        toast.error('Something went wrong adding these categories. Please try again.')
      } finally {
        setIsBulkCreating(false)
      }
    },
    [bulkCreateVisitorCategoriesUseCase, loadVisitorCategories, toast],
  )

  return {
    currentUser,
    visitorCategories,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    badgeColorFilter,
    setBadgeColorFilter: changeBadgeColorFilter,
    ndaRequirementFilter,
    setNdaRequirementFilter: changeNdaRequirementFilter,
    escortRequirementFilter,
    setEscortRequirementFilter: changeEscortRequirementFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
    isBulkAddOpen,
    openBulkAdd,
    closeBulkAdd,
    isBulkCreating,
    bulkCreateResult,
    submitBulkAdd,
  }
}
