import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useToast } from '../components/toast/toast-context'
import { useNotificationCenter } from '../context/notification-center-context'
import { usePageRefresh } from '../context/refresh-context'
import { usePolling } from './use-polling'

const POLL_INTERVAL_MS = 15_000

export interface LiveResource<T> {
  data: T | undefined
  // The most recent load failed. With no `data` yet, that was the initial
  // load; otherwise a background refresh, and `data` is the last good value.
  hasError: boolean
  isLoading: boolean
  lastSuccessAt: Date | undefined
  load: () => Promise<void>
}

// One independently re-fetchable piece of dashboard data. `key` names what is
// being fetched (e.g. branch + range); when it changes the resource re-fetches
// while keeping its current data on screen. Responses to a superseded request
// are dropped, so a slow 7-day response can't overwrite a newer 30-day one.
export function useLiveResource<T>(fetcher: () => Promise<T>, key: string, enabled: boolean): LiveResource<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [lastSuccessAt, setLastSuccessAt] = useState<Date | undefined>(undefined)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setIsLoading(true)
    try {
      const result = await fetcherRef.current()
      if (requestId !== requestIdRef.current) return
      setData(result)
      setHasError(false)
      setLastSuccessAt(new Date())
    } catch {
      if (requestId !== requestIdRef.current) return
      setHasError(true)
    } finally {
      if (requestId === requestIdRef.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (enabled) void load()
  }, [enabled, key, load])

  return { data, hasError, isLoading, lastSuccessAt, load }
}

interface LiveDashboardState {
  // An initial load failed: show the page-level error with "Try again".
  hasInitialError: boolean
  isInitialLoading: boolean
  retry: () => void
}

// Keeps a dashboard's resources live (live-data-refresh): polls every 15 s
// while the tab is visible, re-fetches on return to the tab and on new
// invitation notifications, and registers with the shared top-bar refresh
// control. A failure toasts once per outage rather than on every tick; while
// background refreshes keep failing the last data stays and the control
// shows that it is retrying.
export function useLiveDashboard(resources: LiveResource<unknown>[], errorText: string, enabled: boolean): LiveDashboardState {
  const toast = useToast()
  const { onInvitationActivity } = useNotificationCenter()
  const resourcesRef = useRef(resources)
  resourcesRef.current = resources

  const refreshAll = useCallback(() => {
    resourcesRef.current.forEach((resource) => void resource.load())
  }, [])

  usePolling(refreshAll, { intervalMs: POLL_INTERVAL_MS, isBusy: !enabled, refetchOn: onInvitationActivity })

  const anyError = resources.some((resource) => resource.hasError)
  const wasErroringRef = useRef(false)
  useEffect(() => {
    if (anyError && !wasErroringRef.current) toast.error(errorText)
    wasErroringRef.current = anyError
  }, [anyError, errorText, toast])

  const hasInitialError = resources.some((resource) => resource.hasError && resource.data === undefined)
  const isInitialLoading = !hasInitialError && resources.some((resource) => resource.data === undefined)
  const isRefreshing = resources.some((resource) => resource.isLoading)
  const successTimes = resources.map((resource) => resource.lastSuccessAt?.getTime() ?? 0)
  const oldestSuccess = Math.min(...successTimes)
  // Memoized on the timestamp: the page consumes the refresh context it
  // publishes into, so a fresh Date each render would re-publish forever.
  const lastUpdatedAt = useMemo(() => (oldestSuccess > 0 ? new Date(oldestSuccess) : undefined), [oldestSuccess])

  usePageRefresh({
    refresh: refreshAll,
    isRefreshing,
    lastUpdatedAt,
    hasFailed: anyError && !hasInitialError,
  })

  return { hasInitialError, isInitialLoading, retry: refreshAll }
}
