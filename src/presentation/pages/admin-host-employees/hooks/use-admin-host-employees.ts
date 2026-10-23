import { useCallback, useMemo, useState } from 'react'
import { ApiError } from '../../../../data/api/api-error'
import { useToast } from '../../../components/toast/toast-context'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

const PAGE_SIZE = 20
const EMPTY_EMPLOYEES: HostEmployee[] = []
const EMPTY_DEPARTMENTS: Department[] = []
const EMPTY_ROLE_OPTIONS: string[] = []

export function useAdminHostEmployees() {
  const {
    listHostEmployeesPageUseCase,
    listDepartmentsUseCase,
    listRolesUseCase,
    disableHostEmployeeUseCase,
    enableHostEmployeeUseCase,
    deleteHostEmployeeUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()
  const [pendingDelete, setPendingDelete] = useState<HostEmployee | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [busyEmployeeId, setBusyEmployeeId] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // Polls skip while a delete dialog is open or an action is in flight, so a
  // poll can't swap the rows underneath it. Departments and role names (the
  // filters) load once.
  const resource = useLiveResource({
    load: () =>
      listHostEmployeesPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        departmentId: departmentFilter || undefined,
        role: roleFilter || undefined,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
      }),
    query: { page, departmentFilter, roleFilter, statusFilter },
    reference: async () => {
      const [departments, roles] = await Promise.all([listDepartmentsUseCase.execute(), listRolesUseCase.execute()])
      return { departments, roleOptions: [...new Set(roles.map((role) => role.name))].sort((a, b) => a.localeCompare(b)) }
    },
    errorMessage: 'Something went wrong loading the employees. Please try again.',
    isBusy: pendingDelete !== undefined || isDeleting || busyEmployeeId !== undefined,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const hostEmployees = resource.data?.items ?? EMPTY_EMPLOYEES
  const total = resource.data?.total ?? 0
  const departments = resource.reference?.departments ?? EMPTY_DEPARTMENTS
  const roleOptions = resource.reference?.roleOptions ?? EMPTY_ROLE_OPTIONS

  // 404 = already deleted elsewhere, so the list is stale; 409 (self / last
  // admin) and 403 carry the backend's own message, shown as-is.
  const reportActionError = useCallback(
    (error: unknown, fallback: string) => {
      if (error instanceof ApiError && error.status === 404) {
        toast.error('This employee no longer exists. The list has been refreshed.')
        void reload()
        return
      }
      toast.error(error instanceof ApiError ? error.message : fallback)
    },
    [toast, reload],
  )

  const setEmployeeActive = useCallback(
    async (employee: HostEmployee, active: boolean) => {
      setBusyEmployeeId(employee.id)
      try {
        await (active ? enableHostEmployeeUseCase : disableHostEmployeeUseCase).execute(employee.id)
        toast.success(active ? `${employee.fullName} enabled.` : `${employee.fullName} disabled.`)
        await reload()
      } catch (error) {
        reportActionError(error, `Something went wrong ${active ? 'enabling' : 'disabling'} the employee. Please try again.`)
      } finally {
        setBusyEmployeeId(undefined)
      }
    },
    [enableHostEmployeeUseCase, disableHostEmployeeUseCase, toast, reload, reportActionError],
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
      await reload()
    } catch (error) {
      setPendingDelete(undefined)
      reportActionError(error, 'Something went wrong deleting the employee. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteHostEmployeeUseCase, toast, reload, reportActionError])

  const departmentNameById = useMemo(() => new Map(departments.map((department) => [department.id, department.name])), [departments])

  const isFiltering = departmentFilter !== '' || roleFilter !== '' || statusFilter !== ''

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
  }
}
