import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { VisitorCategoryBulkCreateOut } from '../../../../domain/entities/visitor-category-out-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import { toUserMessage } from '../../../utils/to-user-message'

const PAGE_SIZE = 20
const EMPTY_CATEGORIES: VisitorCategory[] = []

export function useAdminVisitorCategories() {
  const {
    listVisitorCategoriesPageUseCase,
    deleteVisitorCategoryUseCase,
    bulkCreateVisitorCategoriesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

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

  const isActionInProgress = pendingDelete !== undefined || isDeleting || isBulkAddOpen
  const resource = useLiveResource({
    load: () =>
      listVisitorCategoriesPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        badgeColor: badgeColorFilter || undefined,
        ndaRequirement: ndaRequirementFilter || undefined,
        escortRequirement: escortRequirementFilter || undefined,
      }),
    query: { page, badgeColorFilter, ndaRequirementFilter, escortRequirementFilter },
    errorMessage: 'Something went wrong loading the visitor categories. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const visitorCategories = resource.data?.items ?? EMPTY_CATEGORIES
  const total = resource.data?.total ?? 0

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
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the visitor category. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteVisitorCategoryUseCase, toast, reload])

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
          await reload()
        }
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong adding these categories. Please try again.'))
      } finally {
        setIsBulkCreating(false)
      }
    },
    [bulkCreateVisitorCategoriesUseCase, reload, toast],
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
