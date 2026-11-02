import { useEffect, useState } from 'react'
import { ApiError } from '../../data/api/api-error'
import { useAppDependencies } from '../context/app-dependencies-context'
import { usePermissions } from '../context/current-user-context'
import { PAGE_PERMISSIONS } from '../route-permissions'

export type BadgePrintFlowState = 'loading' | 'on' | 'off'

// The badge print flow is shown only when the tenant toggle is on AND the user
// holds `visitors:print_badge`. The server flag is invisible here: a 404 from
// any /checkin route flips the page to its own "unavailable" state. A failed
// tenant read (other than a 403, see below) counts as off - the safe default for a dark-launched feature.
export function useBadgePrintFlow(): BadgePrintFlowState {
  const { getBadgePrintFlowEnabledUseCase, searchCheckinVisitsUseCase } = useAppDependencies()
  const canPrint = usePermissions().can(PAGE_PERMISSIONS.badgePrinting)
  const [enabled, setEnabled] = useState<boolean | undefined>(undefined)

  useEffect(() => {
    if (!canPrint) return
    let cancelled = false
    // Reception holds `visitors:print_badge` but not `tenants:read`, so the
    // tenant read is 403 for them. Fall back to a read-only probe of the
    // search route: 404 = flow off, any other answer = the route is live.
    const probe = () =>
      searchCheckinVisitsUseCase
        .execute({ q: 'a', page: 1, pageSize: 1 })
        .then(() => true)
        .catch((error: unknown) => error instanceof ApiError && error.status !== 404 && error.status < 500 && error.status !== 403)
    getBadgePrintFlowEnabledUseCase
      .execute()
      .catch((error: unknown) => (error instanceof ApiError && error.status === 403 ? probe() : false))
      .then((value) => !cancelled && setEnabled(value))
    return () => {
      cancelled = true
    }
  }, [canPrint, getBadgePrintFlowEnabledUseCase, searchCheckinVisitsUseCase])

  if (!canPrint) return 'off'
  if (enabled === undefined) return 'loading'
  return enabled ? 'on' : 'off'
}
