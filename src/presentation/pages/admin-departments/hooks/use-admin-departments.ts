import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

const PAGE_SIZE = 20

export function useAdminDepartments() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listDepartmentsPageUseCase, listHostEmployeesUseCase, listBranchesUseCase, deleteDepartmentUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [departments, setDepartments] = useState<Department[]>([])
  const [total, setTotal] = useState(0)
  const [branchOptions, setBranchOptions] = useState<{ value: string; label: string }[]>([])
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Department | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [branchFilter, setBranchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/page/retry/refresh/post-mutation - keeps the
  // current rows on screen with a progress cue. `background`: the 15s poll.
  const loadDepartments = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_, employeeList, branches] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listDepartmentsPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
            branchId: branchFilter || undefined,
          }),
          listHostEmployeesUseCase.execute(),
          listBranchesUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setDepartments(page_.items)
        setTotal(page_.total)
        setEmployees(employeeList)
        setBranchOptions(branches.map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)))
        setLastUpdatedAt(new Date())
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the departments. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listDepartmentsPageUseCase, listHostEmployeesUseCase, listBranchesUseCase, page, statusFilter, branchFilter, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadDepartments()
  }, [navigate, loadDepartments])

  const retry = useCallback(() => {
    void loadDepartments()
  }, [loadDepartments])

  // Auto-refreshes the register every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadDepartments('background'), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing, lastUpdatedAt })

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
      await loadDepartments()
    } catch {
      toast.error('Something went wrong deleting the department. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteDepartmentUseCase, toast, loadDepartments])

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
