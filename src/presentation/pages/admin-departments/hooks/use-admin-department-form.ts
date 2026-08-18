import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { DepartmentInput } from '../../../../domain/entities/department-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const EMPTY_VALUES: DepartmentInput = {
  name: '',
  branchId: '',
  headOfDepartment: undefined,
  description: undefined,
  status: 'active',
}

export function useAdminDepartmentForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const { getCurrentStaffUserUseCase, listBranchesUseCase, listDepartmentsUseCase, createDepartmentUseCase, updateDepartmentUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [values, setValues] = useState<DepartmentInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof DepartmentInput, string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, branchList] = await Promise.all([getCurrentStaffUserUseCase.execute(), listBranchesUseCase.execute()])
      setCurrentUser(user)
      setBranches(branchList)

      if (isEditMode) {
        const departments = await listDepartmentsUseCase.execute()
        const department = departments.find((candidate) => candidate.id === id)
        if (!department) {
          setErrorMessage('That department could not be found.')
          return
        }
        setValues({
          name: department.name,
          branchId: department.branchId,
          headOfDepartment: department.headOfDepartment,
          description: department.description,
          status: department.status,
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
  }, [getCurrentStaffUserUseCase, listBranchesUseCase, listDepartmentsUseCase, isEditMode, id, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void load()
  }, [navigate, load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const updateField = useCallback(<K extends keyof DepartmentInput>(key: K, value: DepartmentInput[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof DepartmentInput, string>> = {}
    if (!values.name.trim()) nextErrors.name = 'Department name is required.'
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
      navigate('/admin/departments')
    } catch {
      toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the department. Please try again.`)
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createDepartmentUseCase, updateDepartmentUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/departments')
  }, [navigate])

  return {
    isEditMode,
    currentUser,
    branches,
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
