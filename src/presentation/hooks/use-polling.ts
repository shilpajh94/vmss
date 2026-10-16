import { useEffect, useRef } from 'react'

// Re-fetches triggered by the tab becoming visible or the window regaining
// focus run at most this often - the two events usually fire together.
const RESUME_THROTTLE_MS = 5_000

interface UsePollingOptions {
  intervalMs: number
  isBusy: boolean
  // Extra triggers that re-fetch at once (e.g. the notification center's
  // invitation-activity event). Called with the re-fetch callback; returns
  // its unsubscribe function.
  refetchOn?: (callback: () => void) => () => void
}

// Shared background-refresh convention for operational list/dashboard pages:
// re-runs `fetchSilently` on a fixed interval for as long as the page is
// mounted, skipping a tick while `isBusy` is true (a mutation or dialog is in
// progress) so an automatic refresh never replaces data out from under an
// in-progress user action. Extracted from the pattern already used by
// `use-invitations-board.ts`.
//
// No ticks run while the tab is hidden; returning to the tab or window
// re-fetches immediately (live-data-refresh "Automatic refresh pauses while
// the page is hidden").
export function usePolling(fetchSilently: () => void, { intervalMs, isBusy, refetchOn }: UsePollingOptions): void {
  const isBusyRef = useRef(isBusy)
  isBusyRef.current = isBusy

  const fetchSilentlyRef = useRef(fetchSilently)
  fetchSilentlyRef.current = fetchSilently

  useEffect(() => {
    let lastResumeAt = 0

    const runIfAllowed = () => {
      if (isBusyRef.current || document.visibilityState === 'hidden') return
      fetchSilentlyRef.current()
    }

    const runOnResume = () => {
      if (document.visibilityState !== 'visible') return
      const now = Date.now()
      if (now - lastResumeAt < RESUME_THROTTLE_MS) return
      lastResumeAt = now
      runIfAllowed()
    }

    const intervalId = setInterval(runIfAllowed, intervalMs)
    document.addEventListener('visibilitychange', runOnResume)
    window.addEventListener('focus', runOnResume)
    const unsubscribe = refetchOn?.(runIfAllowed)

    return () => {
      clearInterval(intervalId)
      document.removeEventListener('visibilitychange', runOnResume)
      window.removeEventListener('focus', runOnResume)
      unsubscribe?.()
    }
  }, [intervalMs, refetchOn])
}
