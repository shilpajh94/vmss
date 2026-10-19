import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '../components/toast/toast-context'
import { useNotificationCenter } from '../context/notification-center-context'
import { usePageRefresh } from '../context/refresh-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from './use-polling'


export interface LiveResource<T> {
  data: T | undefined
  // The most recent load failed. With no `data` yet, that was the initial
  // load; otherwise a background refresh, and `data` is the last good value.
  hasError: boolean
  isLoading: boolean
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

  return { data, hasError, isLoading, load }
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

  usePolling(refreshAll, { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: !enabled, refetchOn: onInvitationActivity })

  const anyError = resources.some((resource) => resource.hasError)
  const wasErroringRef = useRef(false)
  useEffect(() => {
    if (anyError && !wasErroringRef.current) toast.error(errorText)
    wasErroringRef.current = anyError
  }, [anyError, errorText, toast])

  const hasInitialError = resources.some((resource) => resource.hasError && resource.data === undefined)
  const isInitialLoading = !hasInitialError && resources.some((resource) => resource.data === undefined)
  const isRefreshing = resources.some((resource) => resource.isLoading)

  usePageRefresh({
    refresh: refreshAll,
    isRefreshing,
    hasFailed: anyError && !hasInitialError,
  })

  return { hasInitialError, isInitialLoading, retry: refreshAll }
}
