import { useCallback, useEffect, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { ApiError } from '../../../../data/api/api-error'
import { usePermissions } from '../../../context/current-user-context'

// Toggling needs `tenants:update`; without it the card is hidden. A failed
// save reverts the switch and shows the server's message.
export function useBadgePrintFlowSetting() {
  const { getBadgePrintFlowEnabledUseCase, setBadgePrintFlowEnabledUseCase } = useAppDependencies()
  const toast = useToast()
  const canManage = usePermissions().can('tenants:update')

  const [enabled, setEnabled] = useState<boolean | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)
    try {
      setEnabled(await getBadgePrintFlowEnabledUseCase.execute())
    } catch {
      setErrorMessage('Something went wrong loading the badge printing setting.')
    } finally {
      setIsLoading(false)
    }
  }, [getBadgePrintFlowEnabledUseCase])

  useEffect(() => {
    if (canManage) void load()
  }, [canManage, load])

  const change = useCallback(
    async (next: boolean) => {
      const previous = enabled
      setEnabled(next)
      setIsSaving(true)
      try {
        await setBadgePrintFlowEnabledUseCase.execute(next)
        toast.success(next ? 'Badge printing turned on.' : 'Badge printing turned off.')
      } catch (error) {
        setEnabled(previous)
        toast.error(error instanceof ApiError ? error.message : 'Something went wrong saving the setting. Please try again.')
      } finally {
        setIsSaving(false)
      }
    },
    [enabled, setBadgePrintFlowEnabledUseCase, toast],
  )

  return { enabled, canManage, isLoading, errorMessage, isSaving, retry: load, change }
}
