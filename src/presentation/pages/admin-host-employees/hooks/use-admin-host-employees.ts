import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20

export function useAdminHostEmployees() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listHostEmployeesPageUseCase, listDepartmentsUseCase, listRolesUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [total, setTotal] = useState(0)
  const [departments, setDepartments] = useState<Department[]>([])
  const [roleOptions, setRoleOptions] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const loadHostEmployees = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, page_, departmentList, roles] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listHostEmployeesPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            departmentId: departmentFilter || undefined,
            role: roleFilter || undefined,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
          }),
          listDepartmentsUseCase.execute(),
          listRolesUseCase.execute(),
        ])
        setCurrentUser(user)
        setHostEmployees(page_.items)
        setTotal(page_.total)
        setDepartments(departmentList)
        setRoleOptions([...new Set(roles.map((role) => role.name))].sort((a, b) => a.localeCompare(b)))
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the employees. Please try again.')
        }
        toast.error('Something went wrong loading the employees. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listHostEmployeesPageUseCase, listDepartmentsUseCase, listRolesUseCase, page, departmentFilter, roleFilter, statusFilter, toast],
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

  // Auto-refreshes the directory every 15s; there's no form/delete dialog
  // state on this page to protect, so polling is never suppressed.
  usePolling(() => void loadHostEmployees({ silent: true }), { intervalMs: 15_000, isBusy: false })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

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
    hostEmployees,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    departmentNameById,
    isLoading,
    errorMessage,
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
