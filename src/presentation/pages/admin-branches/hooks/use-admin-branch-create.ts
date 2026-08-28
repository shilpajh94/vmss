import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

export type BranchCreateValues = Omit<Branch, 'id'>

const EMPTY_VALUES: BranchCreateValues = {
  name: '',
  code: '',
  city: '',
  country: '',
  address: '',
  contactPersonUserId: '',
  contactEmail: '',
  contactPhone: '',
  operatingHoursFrom: undefined,
  operatingHoursTo: undefined,
  notes: undefined,
  isActive: true,
}

const REQUIRED_FIELDS: Array<{ key: keyof BranchCreateValues; message: string }> = [
  { key: 'name', message: 'Branch name is required.' },
  { key: 'code', message: 'Branch code is required.' },
  { key: 'city', message: 'Location/city is required.' },
  { key: 'country', message: 'Country is required.' },
  { key: 'address', message: 'Physical address is required.' },
  { key: 'contactPersonUserId', message: 'Contact person is required.' },
  { key: 'contactEmail', message: 'Contact email is required.' },
  { key: 'contactPhone', message: 'Contact phone is required.' },
]

export function useAdminBranchCreate() {
  const navigate = useNavigate()
  const { createBranchUseCase, getCurrentStaffUserUseCase, listHostEmployeesUseCase } = useAppDependencies()
  const toast = useToast()

  const [values, setValues] = useState<BranchCreateValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<keyof BranchCreateValues, string>>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [employees, setEmployees] = useState<HostEmployee[]>([])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void getCurrentStaffUserUseCase.execute().then(setCurrentUser).catch(() => undefined)
    void listHostEmployeesUseCase.execute().then(setEmployees).catch(() => undefined)
  }, [navigate, getCurrentStaffUserUseCase, listHostEmployeesUseCase])

  const updateField = useCallback(<K extends keyof BranchCreateValues>(key: K, value: BranchCreateValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors: Partial<Record<keyof BranchCreateValues, string>> = {}
    for (const field of REQUIRED_FIELDS) {
      const value = values[field.key]
      if (!value || (typeof value === 'string' && !value.trim())) {
        nextErrors[field.key] = field.message
      }
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      await createBranchUseCase.execute(values)
      navigate('/admin/branches')
      toast.success('Branch created.')
    } catch {
      toast.error('Something went wrong creating the branch. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [values, createBranchUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/branches')
  }, [navigate])

  return {
    currentUser,
    employees,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  }
}
