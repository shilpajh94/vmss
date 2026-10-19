import { useCallback, useRef, useState } from 'react'

// 'initial' - nothing loaded yet (first load in flight, or retrying after a
//             failed first load): show a skeleton.
// 'ready'   - data has loaded at least once: keep showing it from now on.
// 'error'   - the first load failed and there is nothing to keep showing.
export type LoadPhase = 'initial' | 'ready' | 'error'

// 'user'       - filter/page/search/sort/retry/manual refresh/post-mutation
//                reload: shows the in-progress cue once data exists.
// 'background' - automatic polling: no cue at all.
export type LoadMode = 'user' | 'background'

export interface LoadRequest {
  // True when this is the first load (no data shown yet), so the caller
  // can decide whether a failure warrants the full-region error state.
  isInitial: boolean
  // Marks the request settled. Each returns false - and changes nothing -
  // when a newer request has superseded this one, so the caller can bail
  // out before writing a stale response into state.
  succeed: () => boolean
  fail: () => boolean
}

// Splits a view's load state into "first load" vs "refresh"
// (async-ui-states "Re-fetching keeps existing content visible") and
// drops superseded responses ("Out-of-order responses never overwrite
// newer results"). Generalised from useLiveResource's requestIdRef.
// Page hooks keep their own data state; only the loading bookkeeping
// moves here:
//
//   const request = tracker.begin(mode)
//   try {
//     const result = await fetch()
//     if (!request.succeed()) return
//     setItems(result)
//   } catch {
//     if (!request.fail()) return
//     toast.error(...)
//   }
export function useLoadTracker() {
  const [phase, setPhase] = useState<LoadPhase>('initial')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const latestRequestIdRef = useRef(0)
  const hasLoadedRef = useRef(false)

  const begin = useCallback((mode: LoadMode = 'user'): LoadRequest => {
    const requestId = ++latestRequestIdRef.current
    const isInitial = !hasLoadedRef.current
    if (isInitial) {
      setPhase('initial')
    } else if (mode === 'user') {
      setIsRefreshing(true)
    }

    const isCurrent = () => requestId === latestRequestIdRef.current

    return {
      isInitial,
      succeed: () => {
        if (!isCurrent()) return false
        hasLoadedRef.current = true
        setPhase('ready')
        setIsRefreshing(false)
        return true
      },
      fail: () => {
        if (!isCurrent()) return false
        if (!hasLoadedRef.current) setPhase('error')
        setIsRefreshing(false)
        return true
      },
    }
  }, [])

  return { phase, isRefreshing, begin }
}
