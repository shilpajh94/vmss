import { useCallback, useEffect, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { toUserMessage } from '../../../utils/to-user-message'

export type BranchFormState = { mode: 'edit'; branch: Branch } | undefined

const PAGE_SIZE = 20

export function useAdminBranches() {
  const {
    getCurrentStaffUserUseCase,
    listBranchesPageUseCase,
    listHostEmployeesUseCase,
    updateBranchUseCase,
    deleteBranchUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [total, setTotal] = useState(0)
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()

  const [formState, setFormState] = useState<BranchFormState>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<Branch | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/page/retry/refresh/post-mutation - keeps the
  // current rows on screen with a progress cue. `background`: the 15s poll.
  const loadBranches = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_, employeeList] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listBranchesPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
          }),
          listHostEmployeesUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setBranches(page_.items)
        setTotal(page_.total)
        setEmployees(employeeList)
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the branches. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listBranchesPageUseCase, listHostEmployeesUseCase, page, statusFilter, toast],
  )

  useEffect(() => {
    void loadBranches()
  }, [loadBranches])

  const retry = useCallback(() => {
    void loadBranches()
  }, [loadBranches])

  // Auto-refreshes the register every 15s; skipped while a form/delete dialog
  // is open so a background tick can't replace data underneath it.
  const isActionInProgress = formState !== undefined || isSaving || pendingDelete !== undefined || isDeleting
  usePolling(() => void loadBranches('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

  const openEditForm = useCallback((branch: Branch) => {
    setFormState({ mode: 'edit', branch })
  }, [])

  const closeForm = useCallback(() => {
    setFormState(undefined)
  }, [])

  const saveBranch = useCallback(
    async (input: Omit<Branch, 'id'>) => {
      if (!formState) return

      setIsSaving(true)
      try {
        const updated = await updateBranchUseCase.execute(formState.branch.id, input)
        setBranches((current) => current.map((branch) => (branch.id === updated.id ? updated : branch)))
        toast.success('Branch updated.')
        setFormState(undefined)
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong saving the branch. Please try again.'))
      } finally {
        setIsSaving(false)
      }
    },
    [formState, updateBranchUseCase, toast],
  )

  const requestDelete = useCallback((branch: Branch) => {
    setPendingDelete(branch)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteBranchUseCase.execute(pendingDelete.id)
      toast.success('Branch deleted.')
      setPendingDelete(undefined)
      await loadBranches()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the branch. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBranchUseCase, toast, loadBranches])

  const isFiltering = statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  return {
    currentUser,
    branches,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    employees,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    formState,
    isSaving,
    openEditForm,
    closeForm,
    saveBranch,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
