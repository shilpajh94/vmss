import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { toUserMessage } from '../../../utils/to-user-message'

type DepartmentInput = Omit<Department, 'id' | 'branchName'>

const EMPTY_VALUES: DepartmentInput = {
  name: '',
  code: '',
  branchId: '',
  floorId: undefined,
  headOfDepartmentUserId: undefined,
  description: undefined,
  isActive: true,
}

export function useAdminDepartmentForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const {
    getCurrentStaffUserUseCase,
    listBranchesUseCase,
    listDepartmentsUseCase,
    listHostEmployeesUseCase,
    createDepartmentUseCase,
    updateDepartmentUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<DepartmentInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof DepartmentInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, branchList, employeeList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBranchesUseCase.execute({ activeOnly: !isEditMode }),
        listHostEmployeesUseCase.execute(),
      ])
      setCurrentUser(user)
      setBranches(branchList)
      setEmployees(employeeList)

      if (isEditMode) {
        const departments = await listDepartmentsUseCase.execute()
        const department = departments.find((candidate) => candidate.id === id)
        if (!department) {
          setErrorMessage('That department could not be found.')
          return
        }
        setValues({
          name: department.name,
          code: department.code,
          branchId: department.branchId,
          floorId: department.floorId,
          headOfDepartmentUserId: department.headOfDepartmentUserId,
          description: department.description,
          isActive: department.isActive,
        })
      } else {
        setValues(EMPTY_VALUES)
      }
    } catch {
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBranchesUseCase, listDepartmentsUseCase, listHostEmployeesUseCase, isEditMode, id, toast])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: values, isLoading, reload: retry })

  const updateField = useCallback(<K extends keyof DepartmentInput>(key: K, value: DepartmentInput[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof DepartmentInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Department name is required.'
    if (!values.code.trim()) nextErrors.code = 'Department code is required.'
    if (!values.branchId.trim()) nextErrors.branchId = 'Branch is required.'

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateDepartmentUseCase.execute(id, values)
        toast.success('Department updated.')
      } else {
        await createDepartmentUseCase.execute(values)
        toast.success('Department created.')
      }
      release()
      navigate('/admin/departments')
    } catch (error) {
      toast.error(toUserMessage(error, `Something went wrong ${isEditMode ? 'updating' : 'creating'} the department. Please try again.`))
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createDepartmentUseCase, updateDepartmentUseCase, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/departments')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    branches,
    employees,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  }
}
