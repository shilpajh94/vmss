import { useCallback, useMemo, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { toUserMessage } from '../../../utils/to-user-message'

const PAGE_SIZE = 20
const EMPTY_DEPARTMENTS: Department[] = []
const EMPTY_EMPLOYEES: HostEmployee[] = []

export function useAdminDepartments() {
  const { listDepartmentsPageUseCase, listHostEmployeesUseCase, listBranchesUseCase, deleteDepartmentUseCase } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

  const [pendingDelete, setPendingDelete] = useState<Department | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [branchFilter, setBranchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Polls skip while a delete dialog is open, so a background tick can't
  // replace data underneath it. Employees and branch options load once.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listDepartmentsPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
        branchId: branchFilter || undefined,
      }),
    query: { page, statusFilter, branchFilter },
    reference: async () => {
      const [employees, branches] = await Promise.all([listHostEmployeesUseCase.execute(), listBranchesUseCase.execute()])
      return { employees, branches }
    },
    errorMessage: 'Something went wrong loading the departments. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const departments = resource.data?.items ?? EMPTY_DEPARTMENTS
  const total = resource.data?.total ?? 0
  const employees = resource.reference?.employees ?? EMPTY_EMPLOYEES
  const branchOptions = useMemo(
    () =>
      (resource.reference?.branches ?? []).map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [resource.reference],
  )

  const requestDelete = useCallback((department: Department) => {
    setPendingDelete(department)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteDepartmentUseCase.execute(pendingDelete.id)
      toast.success('Department deleted.')
      setPendingDelete(undefined)
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the department. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteDepartmentUseCase, toast, reload])

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
    departments,
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
