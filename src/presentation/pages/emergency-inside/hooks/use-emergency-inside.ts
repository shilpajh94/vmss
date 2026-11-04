import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../../../data/api/api-error'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useZoneFeature } from '../../../context/zone-feature-context'
import { useLiveResource } from '../../../hooks/use-live-resource'

/** The full emergency list, grouped by zone, kept fresh by the shared live-refresh contract (the top-bar refresh control reloads it too). */
export function useEmergencyInside() {
  const { getEmergencyInsideUseCase, listBranchesUseCase } = useAppDependencies()
  const { reportDisabled } = useZoneFeature()
  const [branchFilter, setBranchFilter] = useState('')

  const resource = useLiveResource({
    load: () => getEmergencyInsideUseCase.execute(branchFilter || undefined),
    query: { branchFilter },
    reference: () => listBranchesUseCase.execute(),
    errorMessage: (error) =>
      error instanceof ApiError && error.status === 404 ? 'Zone access is not enabled.' : 'Something went wrong loading who is inside. Please try again.',
  })

  const isFeatureOff = resource.phase === 'error' && resource.error instanceof ApiError && resource.error.status === 404
  useEffect(() => {
    if (isFeatureOff) reportDisabled()
  }, [isFeatureOff, reportDisabled])

  // The time the data on screen was last fetched, so staff can judge how stale it is.
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | undefined>(undefined)
  const { data } = resource
  useEffect(() => {
    if (data) setLastLoadedAt(new Date())
  }, [data])

  const branchOptions = useMemo(
    () => (resource.reference ?? []).map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [resource.reference],
  )

  return { ...resource, report: data, isFeatureOff, lastLoadedAt, branchFilter, setBranchFilter, branchOptions }
}
