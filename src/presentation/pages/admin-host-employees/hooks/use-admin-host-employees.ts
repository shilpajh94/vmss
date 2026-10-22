import { useCallback, useMemo, useState } from 'react'
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
  const { listHostEmployeesPageUseCase, listDepartmentsUseCase, listRolesUseCase } = useAppDependencies()

  const currentUser = useCurrentUser()

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // No dialog on this page to protect, so polling is never suppressed.
  // Departments and role names (the filters) load once.
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
  })
  const { phase, isRefreshing, retry } = resource
  const hostEmployees = resource.data?.items ?? EMPTY_EMPLOYEES
  const total = resource.data?.total ?? 0
  const departments = resource.reference?.departments ?? EMPTY_DEPARTMENTS
  const roleOptions = resource.reference?.roleOptions ?? EMPTY_ROLE_OPTIONS

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
