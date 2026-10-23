import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '../components/toast/toast-context'
import { usePageRefresh } from '../context/refresh-context'
import { LiveResourceController, type LiveResourceState } from './live-resource-controller'
import type { LoadMode } from './use-load-tracker'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from './use-polling'

interface UseLiveResourceOptions<T, R> {
  // The page's changing data (list rows, board columns).
  load: () => Promise<T>
  // Option lists, names and other slow-changing data: loaded once per mount
  // and on a manual refresh, never on a poll.
  reference?: () => Promise<R>
  // What `load` depends on (page, filters, sort). A change re-loads at once
  // as a user load, keeping the current rows on screen with a cue.
  query?: unknown
  // Toasted for a failed initial or user-mode load, never for a poll. A
  // function picks the wording from the error (e.g. a 403's own message).
  errorMessage: string | ((error: unknown) => string)
  pollMs?: number
  // Skips polls while a dialog or mutation is in progress.
  isBusy?: boolean
  refetchOn?: (callback: () => void) => () => void
  // False while the page is still deciding whether it may load at all.
  enabled?: boolean
  // False when the caller registers the top-bar refresh itself, folding in
  // loads of its own (the board's filter reloads).
  registerRefresh?: boolean
}

export interface LiveResource<T, R> extends LiveResourceState<T, R> {
  // Re-runs everything (reference included), e.g. "Try again".
  retry: () => void
  refresh: () => void
  // Re-runs the data load, e.g. after a save; `background` shows no cue.
  reload: (mode?: LoadMode) => Promise<void>
  setData: (update: (current: T | undefined) => T | undefined) => void
}

// One fetch-and-poll contract for list pages and the board (design D-W4,
// live-data-refresh): polls every 10 s while the tab is visible, registers
// with the top-bar refresh control (whose "retrying" state is `hasFailed`),
// keeps reference data out of the poll, toasts only the failures the user
// caused, and drops superseded responses.
export function useLiveResource<T, R = undefined>({
  load,
  reference,
  query,
  errorMessage,
  pollMs = LIVE_REFRESH_INTERVAL_MS,
  isBusy = false,
  refetchOn,
  enabled = true,
  registerRefresh = true,
}: UseLiveResourceOptions<T, R>): LiveResource<T, R> {
  const toast = useToast()
  const errorMessageRef = useRef(errorMessage)
  errorMessageRef.current = errorMessage

  const [controller] = useState(
    () => new LiveResourceController<T, R>({ load, reference, onChange: () => undefined }),
  )
  const [state, setState] = useState<LiveResourceState<T, R>>(() => controller.getState())

  // The latest closures, without restarting a load.
  controller.setOptions({
    load,
    reference,
    onChange: setState,
    onError: (error) => {
      const message = errorMessageRef.current
      toast.error(typeof message === 'function' ? message(error) : message)
    },
  })

  const hasStartedRef = useRef(false)
  const queryKey = JSON.stringify(query ?? null)

  useEffect(() => {
    if (!enabled) return
    if (!hasStartedRef.current) {
      hasStartedRef.current = true
      void controller.start()
    } else {
      void controller.load('user')
    }
  }, [controller, enabled, queryKey])

  const retry = useCallback(() => void controller.refresh(), [controller])
  const reload = useCallback((mode: LoadMode = 'user') => controller.load(mode), [controller])
  const setData = useCallback((update: (current: T | undefined) => T | undefined) => controller.setData(update), [controller])

  usePolling(() => void controller.poll(), { intervalMs: pollMs, isBusy: isBusy || !enabled, refetchOn })

  usePageRefresh(
    registerRefresh
      ? { refresh: retry, isRefreshing: state.phase === 'initial' || state.isRefreshing, hasFailed: state.hasFailed }
      : undefined,
  )

  return { ...state, retry, refresh: retry, reload, setData }
}
