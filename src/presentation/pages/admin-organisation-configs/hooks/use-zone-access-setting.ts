import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../../../data/api/api-error'
import { useToast } from '../../../components/toast/toast-context'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { usePermissions } from '../../../context/current-user-context'
import { useZoneFeature } from '../../../context/zone-feature-context'

// The tenant's zone access control switch. Needs `tenants:update`; without it
// the card is hidden. A failed save reverts the switch and shows the server's
// message. After a save the zone feature probe re-runs so the sidebar picks
// the change up without a reload.
export function useZoneAccessSetting() {
  const { getZoneAccessEnabledUseCase, setZoneAccessEnabledUseCase } = useAppDependencies()
  const toast = useToast()
  const canManage = usePermissions().can('tenants:update')
  const { recheck } = useZoneFeature()

  const [enabled, setEnabled] = useState<boolean | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)
    try {
      setEnabled(await getZoneAccessEnabledUseCase.execute())
    } catch {
      setErrorMessage('Something went wrong loading the zone access setting.')
    } finally {
      setIsLoading(false)
    }
  }, [getZoneAccessEnabledUseCase])

  useEffect(() => {
    if (canManage) void load()
  }, [canManage, load])

  const change = useCallback(
    async (next: boolean) => {
      const previous = enabled
      setEnabled(next)
      setIsSaving(true)
      try {
        await setZoneAccessEnabledUseCase.execute(next)
        toast.success(next ? 'Zone access control turned on.' : 'Zone access control turned off.')
        recheck()
      } catch (error) {
        setEnabled(previous)
        toast.error(error instanceof ApiError ? error.message : 'Something went wrong saving the setting. Please try again.')
      } finally {
        setIsSaving(false)
      }
    },
    [enabled, setZoneAccessEnabledUseCase, toast, recheck],
  )

  return { enabled, canManage, isLoading, errorMessage, isSaving, retry: load, change }
}
