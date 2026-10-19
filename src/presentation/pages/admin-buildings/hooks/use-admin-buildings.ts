import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { Building } from '../../../../domain/entities/building-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20

export function useAdminBuildings() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listBuildingsPageUseCase, listBranchesUseCase, deleteBuildingUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [total, setTotal] = useState(0)
  const [branchOptions, setBranchOptions] = useState<{ value: string; label: string }[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Building | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [branchFilter, setBranchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/page/retry/refresh/post-mutation - keeps the
  // current rows on screen with a progress cue. `background`: the 15s poll.
  const loadBuildings = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_, branches] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listBuildingsPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
            branchId: branchFilter || undefined,
          }),
          listBranchesUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setBuildings(page_.items)
        setTotal(page_.total)
        setBranchOptions(branches.map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)))
        setLastUpdatedAt(new Date())
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the buildings. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listBuildingsPageUseCase, listBranchesUseCase, page, statusFilter, branchFilter, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadBuildings()
  }, [navigate, loadBuildings])

  const retry = useCallback(() => {
    void loadBuildings()
  }, [loadBuildings])

  // Auto-refreshes the registry every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadBuildings('background'), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing, lastUpdatedAt })

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
      await loadBuildings()
    } catch {
      toast.error('Something went wrong deleting the building. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBuildingUseCase, toast, loadBuildings])

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
