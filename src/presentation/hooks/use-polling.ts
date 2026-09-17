import { useEffect, useRef } from 'react'

interface UsePollingOptions {
  intervalMs: number
  isBusy: boolean
}

// Shared background-refresh convention for operational list/dashboard pages:
// re-runs `fetchSilently` on a fixed interval for as long as the page is
// mounted, skipping a tick while `isBusy` is true (a mutation or dialog is in
// progress) so an automatic refresh never replaces data out from under an
// in-progress user action. Extracted from the pattern already used by
// `use-invitations-board.ts`.
export function usePolling(fetchSilently: () => void, { intervalMs, isBusy }: UsePollingOptions): void {
  const isBusyRef = useRef(isBusy)
  isBusyRef.current = isBusy

  const fetchSilentlyRef = useRef(fetchSilently)
  fetchSilentlyRef.current = fetchSilently

  useEffect(() => {
    const intervalId = setInterval(() => {
      if (isBusyRef.current) return
      fetchSilentlyRef.current()
    }, intervalMs)

    return () => clearInterval(intervalId)
  }, [intervalMs])
}
