import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { BranchRoleAssignment, HostEmployee, HostEmployeeCreateInput } from '../../../../domain/entities/host-employee-schema'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const EMPTY_CREATE_VALUES: HostEmployeeCreateInput = {
  fullName: '',
  email: '',
  employeeCode: '',
  phoneNumber: undefined,
  designation: undefined,
  departmentId: undefined,
  roleId: undefined,
  branchId: undefined,
}

export function useAdminHostEmployeeForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    getCurrentStaffUserUseCase,
    listDepartmentsUseCase,
    listBranchesUseCase,
    listHostEmployeesUseCase,
    createHostEmployeeUseCase,
    listRolesUseCase,
    assignHostEmployeeRoleUseCase,
    revokeHostEmployeeRoleUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [departments, setDepartments] = useState<Department[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [employee, setEmployee] = useState<HostEmployee | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [createValues, setCreateValues] = useState<HostEmployeeCreateInput>(EMPTY_CREATE_VALUES)
  const [createErrors, setCreateErrors] = useState<Partial<Record<keyof HostEmployeeCreateInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const [assignRoleId, setAssignRoleId] = useState('')
  const [assignBranchId, setAssignBranchId] = useState('')
  const [isAssigning, setIsAssigning] = useState(false)
  const [revokingAssignmentId, setRevokingAssignmentId] = useState<string | undefined>(undefined)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, departmentList, branchList, roleList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listDepartmentsUseCase.execute(),
        listBranchesUseCase.execute(),
        listRolesUseCase.execute(),
      ])
      setCurrentUser(user)
      setDepartments(departmentList)
      setBranches(branchList)
      setRoles(roleList)

      if (isEditMode) {
        const hostEmployees = await listHostEmployeesUseCase.execute()
        const found = hostEmployees.find((candidate) => candidate.id === id)
        if (!found) {
          setErrorMessage('That host employee could not be found.')
          return
        }
        setEmployee(found)
      } else {
        setCreateValues(EMPTY_CREATE_VALUES)
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listDepartmentsUseCase, listBranchesUseCase, listRolesUseCase, listHostEmployeesUseCase, isEditMode, id, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void load()
  }, [navigate, load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const departmentName = useMemo(
    () => (employee?.departmentId ? departments.find((department) => department.id === employee.departmentId)?.name : undefined),
    [employee, departments],
  )

  // Create mode

  const updateCreateField = useCallback(<K extends keyof HostEmployeeCreateInput>(key: K, value: HostEmployeeCreateInput[K]) => {
    setCreateValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submitCreate = useCallback(async () => {
    const nextErrors: Partial<Record<keyof HostEmployeeCreateInput, string>> = {}
    if (!createValues.fullName.trim()) nextErrors.fullName = 'Employee name is required.'
    if (!createValues.email.trim()) nextErrors.email = 'Email address is required.'
    if (!createValues.employeeCode.trim()) nextErrors.employeeCode = 'Employee code is required.'

    if (Object.keys(nextErrors).length > 0) {
      setCreateErrors(nextErrors)
      return
    }
    setCreateErrors({})

    setIsSaving(true)
    try {
      await createHostEmployeeUseCase.execute({
        ...createValues,
        fullName: createValues.fullName.trim(),
        email: createValues.email.trim(),
        employeeCode: createValues.employeeCode.trim(),
      })
      toast.success('Host employee created.')
      navigate('/admin/host-employees')
    } catch {
      toast.error('Something went wrong creating the host employee. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [createValues, createHostEmployeeUseCase, navigate, toast])

  // Edit mode: role/branch assignment management

  const assignRole = useCallback(async () => {
    if (!employee || !assignRoleId) return

    setIsAssigning(true)
    try {
      const assigned: BranchRoleAssignment = await assignHostEmployeeRoleUseCase.execute(
        employee.id,
        assignRoleId,
        assignBranchId || undefined,
      )
      setEmployee((current) => (current ? { ...current, branchRoles: [...current.branchRoles, assigned] } : current))
      setAssignRoleId('')
      setAssignBranchId('')
      toast.success('Role assigned.')
    } catch {
      toast.error('Something went wrong assigning the role. Please try again.')
    } finally {
      setIsAssigning(false)
    }
  }, [employee, assignRoleId, assignBranchId, assignHostEmployeeRoleUseCase, toast])

  const revokeRole = useCallback(
    async (assignmentId: string) => {
      if (!employee) return

      setRevokingAssignmentId(assignmentId)
      try {
        await revokeHostEmployeeRoleUseCase.execute(employee.id, assignmentId)
        setEmployee((current) =>
          current ? { ...current, branchRoles: current.branchRoles.filter((role) => role.id !== assignmentId) } : current,
        )
        toast.success('Role revoked.')
      } catch {
        toast.error('Something went wrong revoking the role. Please try again.')
      } finally {
        setRevokingAssignmentId(undefined)
      }
    },
    [employee, revokeHostEmployeeRoleUseCase, toast],
  )

  const cancel = useCallback(() => {
    navigate('/admin/host-employees')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    isLoading,
    errorMessage,
    retry,
    roles,
    branches,
    departments,
    // create mode
    createValues,
    createErrors,
    isSaving,
    updateCreateField,
    submitCreate,
    // edit mode
    employee,
    departmentName,
    assignRoleId,
    setAssignRoleId,
    assignBranchId,
    setAssignBranchId,
    isAssigning,
    assignRole,
    revokingAssignmentId,
    revokeRole,
    cancel,
  }
}
