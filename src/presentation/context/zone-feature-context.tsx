import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { PAGE_PERMISSIONS } from '../route-permissions'
import { zoneFeatureStatusForError, type ZoneFeatureStatus } from '../utils/zone-feature'
import { useAppDependencies } from './app-dependencies-context'
import { usePermissions } from './current-user-context'

interface ZoneFeatureValue {
  status: ZoneFeatureStatus
  /** True only once `GET /zones` has succeeded; every zone entry point reads this. */
  enabled: boolean
  /** A page that sees a 404 from the zone API reports it so the rest of the UI hides too. */
  reportDisabled: () => void
  /** Probes `GET /zones` again, e.g. right after the tenant's zone switch is turned on or off. */
  recheck: () => void
}

const ZoneFeatureContext = createContext<ZoneFeatureValue>({ status: 'unknown', enabled: false, reportDisabled: () => {}, recheck: () => {} })

// Probes `GET /zones` once per signed-in session (page size 1). The backend
// answers 404 for everything until ZONE_ACCESS_ENABLED is on, so a 404 hides
// the zone UI. Users without `zones:view` are never probed.
export function ZoneFeatureProvider({ children }: { children: ReactNode }) {
  const { listZonesUseCase } = useAppDependencies()
  const canViewZones = usePermissions().can(PAGE_PERMISSIONS.zones)
  const [status, setStatus] = useState<ZoneFeatureStatus>('unknown')
  const [probeCount, setProbeCount] = useState(0)

  useEffect(() => {
    if (!canViewZones) return
    let cancelled = false
    listZonesUseCase
      .execute({ page: 1, pageSize: 1 })
      .then(() => !cancelled && setStatus('enabled'))
      .catch((error: unknown) => !cancelled && setStatus(zoneFeatureStatusForError(error)))
    return () => {
      cancelled = true
    }
    // `probeCount` re-runs the probe on `recheck`.
  }, [canViewZones, listZonesUseCase, probeCount])

  const value = useMemo<ZoneFeatureValue>(
    () => ({ status, enabled: canViewZones && status === 'enabled', reportDisabled: () => setStatus('disabled'), recheck: () => setProbeCount((count) => count + 1) }),
    [status, canViewZones],
  )
  return <ZoneFeatureContext.Provider value={value}>{children}</ZoneFeatureContext.Provider>
}

export function useZoneFeature(): ZoneFeatureValue {
  return useContext(ZoneFeatureContext)
}
