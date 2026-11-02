import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { ApiError } from '../../../../data/api/api-error'
import type { KioskInput } from '../../../../domain/entities/kiosk-schema'
import { canManageKiosks } from '../can-manage-kiosks'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'

const NAME_MAX = 255
const DESCRIPTION_MAX = 2000

const EMPTY_VALUES: KioskInput = { name: '', description: '', isActive: true }

export function useAdminKioskForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEditMode = id !== undefined

  const { getKioskUseCase, createKioskUseCase, updateKioskUseCase } = useAppDependencies()
  const toast = useToast()
  const currentUser = useCurrentUser()

  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [values, setValues] = useState<KioskInput>(EMPTY_VALUES)
  const [errors, setErrors] = useState<Partial<Record<'name' | 'description', string>>>({})
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      if (!canManageKiosks(currentUser)) {
        toast.error('You do not have permission to manage kiosks.')
        navigate('/admin/kiosks', { replace: true })
        return
      }

      if (isEditMode) {
        const kiosk = await getKioskUseCase.execute(id)
        setValues({ name: kiosk.name, description: kiosk.description ?? '', isActive: kiosk.isActive })
      } else {
        setValues(EMPTY_VALUES)
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        toast.error('That kiosk no longer exists.')
        navigate('/admin/kiosks', { replace: true })
        return
      }
      setErrorMessage('Something went wrong loading this page. Please try again.')
      toast.error('Something went wrong loading this page. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [currentUser, getKioskUseCase, isEditMode, id, navigate, toast])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: values, isLoading, reload: retry })

  const updateField = useCallback(<K extends keyof KioskInput>(key: K, value: KioskInput[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(async () => {
    const name = values.name.trim()
    const description = (values.description ?? '').trim()

    const nextErrors: Partial<Record<'name' | 'description', string>> = {}
    if (!name) nextErrors.name = 'Kiosk name is required.'
    else if (name.length > NAME_MAX) nextErrors.name = `Kiosk name must be ${NAME_MAX} characters or fewer.`
    if (description.length > DESCRIPTION_MAX) nextErrors.description = `Description must be ${DESCRIPTION_MAX} characters or fewer.`

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    const input: KioskInput = { name, description: description || undefined, isActive: values.isActive }

    setIsSaving(true)
    try {
      if (isEditMode) {
        await updateKioskUseCase.execute(id, input)
        toast.success('Kiosk updated.')
      } else {
        await createKioskUseCase.execute(input)
        toast.success('Kiosk created.')
      }
      release()
      navigate('/admin/kiosks')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setErrors({ name: 'A kiosk with this name already exists.' })
      } else if (error instanceof ApiError && error.status === 404) {
        toast.error('That kiosk no longer exists.')
        release()
        navigate('/admin/kiosks', { replace: true })
      } else if (error instanceof ApiError && (error.status === 403 || error.status === 422)) {
        toast.error(error.message)
      } else {
        toast.error(`Something went wrong ${isEditMode ? 'updating' : 'creating'} the kiosk. Please try again.`)
      }
    } finally {
      setIsSaving(false)
    }
  }, [values, isEditMode, id, createKioskUseCase, updateKioskUseCase, navigate, toast, release])

  const cancel = useCallback(() => {
    navigate('/admin/kiosks')
  }, [navigate])

  return { isEditMode, isLoading, errorMessage, retry, values, errors, isSaving, updateField, submit, cancel }
}
