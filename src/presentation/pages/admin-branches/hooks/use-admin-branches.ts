import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { toUserMessage } from '../../../utils/to-user-message'

export type BranchFormState = { mode: 'edit'; branch: Branch } | undefined

const PAGE_SIZE = 20
const EMPTY_BRANCHES: Branch[] = []
const EMPTY_EMPLOYEES: HostEmployee[] = []

export function useAdminBranches() {
  const {
    listBranchesPageUseCase,
    listHostEmployeesUseCase,
    updateBranchUseCase,
    deleteBranchUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

  const [formState, setFormState] = useState<BranchFormState>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<Branch | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Polls skip while a form/delete dialog is open, so a background tick can't
  // replace data underneath it. The employee list (contact person) loads once.
  const isActionInProgress = formState !== undefined || isSaving || pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listBranchesPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
      }),
    query: { page, statusFilter },
    reference: () => listHostEmployeesUseCase.execute(),
    errorMessage: 'Something went wrong loading the branches. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload, setData } = resource
  const branches = resource.data?.items ?? EMPTY_BRANCHES
  const total = resource.data?.total ?? 0
  const employees = resource.reference ?? EMPTY_EMPLOYEES

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
        setData((current) => current && { ...current, items: current.items.map((branch) => (branch.id === updated.id ? updated : branch)) })
        toast.success('Branch updated.')
        setFormState(undefined)
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong saving the branch. Please try again.'))
      } finally {
        setIsSaving(false)
      }
    },
    [formState, updateBranchUseCase, toast, setData],
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
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the branch. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBranchUseCase, toast, reload])

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
