import { useCallback, useMemo, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { Building } from '../../../../domain/entities/building-schema'
import { toUserMessage } from '../../../utils/to-user-message'

const PAGE_SIZE = 20
const EMPTY_BUILDINGS: Building[] = []

export function useAdminBuildings() {
  const { listBuildingsPageUseCase, listBranchesUseCase, deleteBuildingUseCase } = useAppDependencies()
  const toast = useToast()
  const currentUser = useCurrentUser()

  const [pendingDelete, setPendingDelete] = useState<Building | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [branchFilter, setBranchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Polls skip while a delete dialog is open, so a background tick can't
  // replace data underneath it. The branch options load once.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listBuildingsPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
        branchId: branchFilter || undefined,
      }),
    query: { page, statusFilter, branchFilter },
    reference: () => listBranchesUseCase.execute(),
    errorMessage: 'Something went wrong loading the buildings. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const buildings = resource.data?.items ?? EMPTY_BUILDINGS
  const total = resource.data?.total ?? 0
  const branchOptions = useMemo(
    () => (resource.reference ?? []).map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [resource.reference],
  )

  const requestDelete = useCallback((building: Building) => {
    setPendingDelete(building)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteBuildingUseCase.execute(pendingDelete.id)
      toast.success('Building deleted.')
      setPendingDelete(undefined)
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the building. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBuildingUseCase, toast, reload])

  const isFiltering = branchFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeBranchFilter = useCallback(
    (value: string) => {
      setBranchFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setBranchFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  return {
    currentUser,
    buildings,
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
    branchOptions,
    branchFilter,
    setBranchFilter: changeBranchFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
