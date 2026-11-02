import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNotificationCenter } from './notification-center-context'

export interface PageRefreshState {
  refresh: () => void
  isRefreshing: boolean
  // True while background refreshes are failing after a successful load:
  // the page keeps its last data and the control says it is retrying
  // (live-data-refresh "Background refresh failures are reported once").
  hasFailed?: boolean
  // Form pages: true while the user has edits that a refresh would discard,
  // so the top-bar control asks before calling `refresh`
  // (live-data-refresh "A manual refresh control remains available").
  hasUnsavedChanges?: boolean
}

interface RefreshContextValue {
  activeRefresh: PageRefreshState
  setActiveRefresh: (state: PageRefreshState | undefined) => void
}

const RefreshContext = createContext<RefreshContextValue | undefined>(undefined)

// Lets the persistent AppTopBar own the one shared manual-refresh control
// while each operational list/dashboard page still controls what "refresh"
// actually does, without the page needing to render (or remount) the control
// itself. Mirrors page-header-context.tsx's provider/registration split.
//
// A page that registers nothing (e.g. a placeholder) still gets a working
// control: the fallback refreshes the shell's shared data, the notification
// feed, so the control is present on every admin and staff page.
export function RefreshProvider({ children }: { children: ReactNode }) {
  const { refresh: refreshNotifications } = useNotificationCenter()
  const [pageRefresh, setActiveRefresh] = useState<PageRefreshState | undefined>(undefined)
  const [isFallbackRefreshing, setIsFallbackRefreshing] = useState(false)

  const refreshShell = useCallback(() => {
    setIsFallbackRefreshing(true)
    void refreshNotifications().finally(() => setIsFallbackRefreshing(false))
  }, [refreshNotifications])

  const activeRefresh = useMemo<PageRefreshState>(
    () => pageRefresh ?? { refresh: refreshShell, isRefreshing: isFallbackRefreshing },
    [pageRefresh, refreshShell, isFallbackRefreshing],
  )
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

// Called by a page's data hook to publish its refresh function and in-flight
// state into the shared top-bar control.
// Re-registers whenever those values change, and clears the registration on
// unmount so navigating to a page that doesn't call this (or away from one
// that does) doesn't leave a stale control behind. `undefined` registers
// nothing, for a shared hook whose caller registers instead.
export function usePageRefresh(state: PageRefreshState | undefined): void {
  const { setActiveRefresh } = useRefreshContext()
  const isRegistered = state !== undefined
  const { refresh, isRefreshing, hasFailed = false, hasUnsavedChanges = false } = state ?? UNREGISTERED

  useEffect(() => {
    if (!isRegistered) return
    setActiveRefresh({ refresh, isRefreshing, hasFailed, hasUnsavedChanges })
    return () => setActiveRefresh(undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRegistered, refresh, isRefreshing, hasFailed, hasUnsavedChanges])
}

const UNREGISTERED: PageRefreshState = { refresh: () => undefined, isRefreshing: false }
