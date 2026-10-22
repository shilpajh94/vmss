import { useCallback, useEffect, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { ApiError } from '../../../../data/api/api-error'
import { usePermissions } from '../../../context/current-user-context'

// Editing needs `settings:manage`; the backend still enforces it and a 403 on
// save surfaces as an error toast. A 403 on load (no `settings:view`) hides
// the setting entirely.
export function useKioskLocationValidation() {
  const { getKioskLocationValidationUseCase, updateKioskLocationValidationUseCase } = useAppDependencies()
  const toast = useToast()

  const [enforce, setEnforce] = useState<boolean | undefined>(undefined)
  const canManage = usePermissions().can('settings:manage')
  const [isVisible, setIsVisible] = useState(true)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)
    try {
      setEnforce(await getKioskLocationValidationUseCase.execute())
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setIsVisible(false)
      } else {
        setErrorMessage('Something went wrong loading the kiosk location setting.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [getKioskLocationValidationUseCase])

  useEffect(() => {
    void load()
  }, [load])

  const change = useCallback(
    async (next: boolean) => {
      const previous = enforce
      setEnforce(next)
      setIsSaving(true)
      try {
        setEnforce(await updateKioskLocationValidationUseCase.execute(next))
        toast.success('Kiosk location validation updated.')
      } catch (error) {
        setEnforce(previous)
        toast.error(error instanceof ApiError && error.status === 403 ? error.message : 'Something went wrong saving the setting. Please try again.')
      } finally {
        setIsSaving(false)
      }
    },
    [enforce, updateKioskLocationValidationUseCase, toast],
  )

  return { enforce, canManage, isVisible, isLoading, errorMessage, isSaving, retry: load, change }
}
