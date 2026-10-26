import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '../../../../data/api/api-error'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useDebouncedValue } from '../../../hooks/use-debounced-value'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300

export function useAdminHostEmployees() {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listHostEmployeesPageUseCase,
    listDepartmentsUseCase,
    listRolesUseCase,
    disableHostEmployeeUseCase,
    enableHostEmployeeUseCase,
    deleteHostEmployeeUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [total, setTotal] = useState(0)
  const [departments, setDepartments] = useState<Department[]>([])
  const [roleOptions, setRoleOptions] = useState<string[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [pendingDelete, setPendingDelete] = useState<HostEmployee | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [busyEmployeeId, setBusyEmployeeId] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS).trim()

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Re-anchors to page 1 when the *debounced* search changes (not per
  // keystroke). Adjusted during render so the load below runs once, with the
  // new search and page 1, instead of once per state change.
  const [appliedSearch, setAppliedSearch] = useState(debouncedSearch)
  if (appliedSearch !== debouncedSearch) {
    setAppliedSearch(debouncedSearch)
    resetToFirstPage()
  }

  // `user` (default): filter/page/retry/refresh - keeps the current rows on
  // screen with a progress cue. `background`: the 15s poll.
  const loadHostEmployees = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_, departmentList, roles] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listHostEmployeesPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            departmentId: departmentFilter || undefined,
            role: roleFilter || undefined,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
            search: debouncedSearch || undefined,
          }),
          listDepartmentsUseCase.execute(),
          listRolesUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)
        setHostEmployees(page_.items)
        setTotal(page_.total)
        setDepartments(departmentList)
        setRoleOptions([...new Set(roles.map((role) => role.name))].sort((a, b) => a.localeCompare(b)))
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the employees. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listHostEmployeesPageUseCase, listDepartmentsUseCase, listRolesUseCase, page, departmentFilter, roleFilter, statusFilter, debouncedSearch, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadHostEmployees()
  }, [navigate, loadHostEmployees])

  const retry = useCallback(() => {
    void loadHostEmployees()
  }, [loadHostEmployees])

  // Auto-refreshes the directory every 15s; skipped while a delete dialog is
  // open or an action is in flight so a poll can't swap the rows underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting || busyEmployeeId !== undefined
  usePolling(() => void loadHostEmployees('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  // 404 = already deleted elsewhere, so the list is stale; 409 (self / last
  // admin) and 403 carry the backend's own message, shown as-is.
  const reportActionError = useCallback(
    (error: unknown, fallback: string) => {
      if (error instanceof ApiError && error.status === 404) {
        toast.error('This employee no longer exists. The list has been refreshed.')
        void loadHostEmployees()
        return
      }
      toast.error(error instanceof ApiError ? error.message : fallback)
    },
    [toast, loadHostEmployees],
  )

  const setEmployeeActive = useCallback(
    async (employee: HostEmployee, active: boolean) => {
      setBusyEmployeeId(employee.id)
      try {
        await (active ? enableHostEmployeeUseCase : disableHostEmployeeUseCase).execute(employee.id)
        toast.success(active ? `${employee.fullName} enabled.` : `${employee.fullName} disabled.`)
        await loadHostEmployees()
      } catch (error) {
        reportActionError(error, `Something went wrong ${active ? 'enabling' : 'disabling'} the employee. Please try again.`)
      } finally {
        setBusyEmployeeId(undefined)
      }
    },
    [enableHostEmployeeUseCase, disableHostEmployeeUseCase, toast, loadHostEmployees, reportActionError],
  )

  const requestDelete = useCallback((employee: HostEmployee) => setPendingDelete(employee), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteHostEmployeeUseCase.execute(pendingDelete.id)
      toast.success('Employee deleted.')
      setPendingDelete(undefined)
      await loadHostEmployees()
    } catch (error) {
      setPendingDelete(undefined)
      reportActionError(error, 'Something went wrong deleting the employee. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteHostEmployeeUseCase, toast, loadHostEmployees, reportActionError])

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

  const departmentNameById = useMemo(() => new Map(departments.map((department) => [department.id, department.name])), [departments])

  const isFiltering = departmentFilter !== '' || roleFilter !== '' || statusFilter !== ''
  const isNarrowed = isFiltering || debouncedSearch !== ''

  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeDepartmentFilter = useCallback(
    (value: string) => {
      setDepartmentFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeRoleFilter = useCallback(
    (value: string) => {
      setRoleFilter(value)
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
    setDepartmentFilter('')
    setRoleFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  return {
    currentUser,
    pendingDelete,
    isDeleting,
    busyEmployeeId,
    setEmployeeActive,
    requestDelete,
    cancelDelete,
    confirmDelete,
    hostEmployees,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    departmentNameById,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    departments,
    roleOptions,
    departmentFilter,
    setDepartmentFilter: changeDepartmentFilter,
    roleFilter,
    setRoleFilter: changeRoleFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    isNarrowed,
    search,
    setSearch,
  }
}
