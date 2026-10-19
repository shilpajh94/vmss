import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export interface PageRefreshState {
  refresh: () => void
  isRefreshing: boolean
  lastUpdatedAt: Date | undefined
  // True while background refreshes are failing after a successful load:
  // the page keeps its last data and the control says it is retrying
  // (live-data-refresh "Background refresh failures are reported once").
  hasFailed?: boolean
}

interface RefreshContextValue {
  activeRefresh: PageRefreshState | undefined
  setActiveRefresh: (state: PageRefreshState | undefined) => void
}

const RefreshContext = createContext<RefreshContextValue | undefined>(undefined)

// Lets the persistent AppTopBar own the one shared manual-refresh control
// while each operational list/dashboard page still controls what "refresh"
// actually does, without the page needing to render (or remount) the control
// itself. Mirrors page-header-context.tsx's provider/registration split.
export function RefreshProvider({ children }: { children: ReactNode }) {
  const [activeRefresh, setActiveRefresh] = useState<PageRefreshState | undefined>(undefined)
  const value = useMemo(() => ({ activeRefresh, setActiveRefresh }), [activeRefresh])

  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>
}

export function useRefreshContext(): RefreshContextValue {
  const context = useContext(RefreshContext)
  if (!context) {
    throw new Error('useRefreshContext must be used within a RefreshProvider')
  }
  return context
}

// Called by a page's data hook to publish its refresh function, in-flight
// state, and last-successful-fetch time into the shared top-bar control.
// Re-registers whenever those values change, and clears the registration on
// unmount so navigating to a page that doesn't call this (or away from one
// that does) doesn't leave a stale control behind.
export function usePageRefresh(state: PageRefreshState): void {
  const { setActiveRefresh } = useRefreshContext()
  const { refresh, isRefreshing, lastUpdatedAt, hasFailed = false } = state

  useEffect(() => {
    setActiveRefresh({ refresh, isRefreshing, lastUpdatedAt, hasFailed })
    return () => setActiveRefresh(undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, isRefreshing, lastUpdatedAt, hasFailed])
}
