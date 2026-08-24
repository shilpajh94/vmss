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
      setErrorMessage('Something went wrong loading the host employees. Please try again.')
      toast.error('Something went wrong loading the host employees. Please try again.')
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

  return {
    currentUser,
    hostEmployees,
    departmentNameById,
    isLoading,
    errorMessage,
    retry,
  }
}
