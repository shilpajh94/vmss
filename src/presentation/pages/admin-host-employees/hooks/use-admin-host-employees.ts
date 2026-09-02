import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Department } from '../../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminHostEmployees() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listHostEmployeesUseCase, listDepartmentsUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const loadHostEmployees = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list, departmentList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listHostEmployeesUseCase.execute(),
        listDepartmentsUseCase.execute(),
      ])
      setCurrentUser(user)
      setHostEmployees(list)
      setDepartments(departmentList)
    } catch {
      setErrorMessage('Something went wrong loading the employees. Please try again.')
      toast.error('Something went wrong loading the employees. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listHostEmployeesUseCase, listDepartmentsUseCase, toast])

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

  const departmentNameById = useMemo(() => new Map(departments.map((department) => [department.id, department.name])), [departments])

  const roleOptions = useMemo(() => {
    const roleNames = new Set(hostEmployees.flatMap((employee) => employee.branchRoles.map((role) => role.roleName)))
    return [...roleNames].sort((a, b) => a.localeCompare(b))
  }, [hostEmployees])

  const filteredHostEmployees = useMemo(() => {
    return hostEmployees.filter((employee) => {
      if (departmentFilter && employee.departmentId !== departmentFilter) return false
      if (roleFilter && !employee.branchRoles.some((role) => role.roleName === roleFilter)) return false
      if (statusFilter && (statusFilter === 'active') !== employee.isActive) return false
      return true
    })
  }, [hostEmployees, departmentFilter, roleFilter, statusFilter])

  const isFiltering = departmentFilter !== '' || roleFilter !== '' || statusFilter !== ''

  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => {
    setDepartmentFilter('')
    setRoleFilter('')
    setStatusFilter('')
  }, [])

  return {
    currentUser,
    hostEmployees: filteredHostEmployees,
    hasAnyHostEmployees: hostEmployees.length > 0,
    departmentNameById,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    departments,
    roleOptions,
    departmentFilter,
    setDepartmentFilter,
    roleFilter,
    setRoleFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
  }
}
