import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

export function useAdminDepartments() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listDepartmentsUseCase, listHostEmployeesUseCase, deleteDepartmentUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [departments, setDepartments] = useState<Department[]>([])
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Department | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadDepartments = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list, employeeList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listDepartmentsUseCase.execute(),
        listHostEmployeesUseCase.execute(),
      ])
      setCurrentUser(user)
      setDepartments(list)
      setEmployees(employeeList)
    } catch {
      setErrorMessage('Something went wrong loading the departments. Please try again.')
      toast.error('Something went wrong loading the departments. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listDepartmentsUseCase, listHostEmployeesUseCase, toast])

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
      setDepartments((current) => current.filter((department) => department.id !== pendingDelete.id))
      toast.success('Department deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the department. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteDepartmentUseCase, toast])

  return {
    currentUser,
    departments,
    employees,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
