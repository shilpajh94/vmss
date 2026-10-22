import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { apiFieldErrors, toUserMessage } from '../../../utils/to-user-message'

import { validateBranchValues, type BranchFormErrors, type BranchFormValues } from '../branch-form-validation'

export type BranchCreateValues = BranchFormValues

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

// The API's per-field 422 messages for the fields this form shows.
function pickBranchFieldErrors(error: unknown): BranchFormErrors {
  const fieldErrors = apiFieldErrors(error)
  const errors: BranchFormErrors = {}
  for (const key of Object.keys(EMPTY_VALUES) as Array<keyof BranchFormValues>) {
    if (fieldErrors[key]) errors[key] = fieldErrors[key]
  }
  return errors
}

export function useAdminBranchCreate() {
  const navigate = useNavigate()
  const { createBranchUseCase, listHostEmployeesUseCase } = useAppDependencies()
  const toast = useToast()

  const [values, setValues] = useState<BranchCreateValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<BranchFormErrors>({})
  const [isSaving, setIsSaving] = useState(false)
  const currentUser = useCurrentUser()
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | undefined>(undefined)

  // The contact-person picker needs the employee list; without it the form
  // can't be completed, so a failure shows an error with retry instead of
  // an empty picker.
  const loadReferenceData = useCallback(async () => {
    setIsLoading(true)
    setLoadErrorMessage(undefined)
    try {
      setEmployees(await listHostEmployeesUseCase.execute())
    } catch {
      setLoadErrorMessage('Something went wrong loading the employee list. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [listHostEmployeesUseCase])

  useEffect(() => {
    void loadReferenceData()
  }, [loadReferenceData])

  // A confirmed top-bar refresh empties the form and re-fetches its lists.
  const reload = useCallback(() => {
    setValues(EMPTY_VALUES)
    setErrors({})
    void loadReferenceData()
  }, [loadReferenceData])

  const { release } = useFormPageRefresh({ values, isLoading, reload, baseline: EMPTY_VALUES })

  const updateField = useCallback(<K extends keyof BranchCreateValues>(key: K, value: BranchCreateValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const nextErrors = validateBranchValues(values)
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    setIsSaving(true)
    try {
      await createBranchUseCase.execute(values)
      release()
      navigate('/admin/branches')
      toast.success('Branch created.')
    } catch (error) {
      setErrors(pickBranchFieldErrors(error))
      toast.error(toUserMessage(error, 'Something went wrong creating the branch. Please try again.'))
    } finally {
      setIsSaving(false)
    }
  }, [values, createBranchUseCase, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/branches')
  }, [navigate])

  const retry = useCallback(() => {
    void loadReferenceData()
  }, [loadReferenceData])

  return {
    currentUser,
    employees,
    isLoading,
    loadErrorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  }
}
