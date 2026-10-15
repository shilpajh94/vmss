import { createContext, useContext } from 'react'

interface SidebarCollapseContextValue {
  /** True only when docked at desktop width and collapsed to the icon rail. */
  isCollapsed: boolean
  toggleCollapsed: () => void
}

// Provided by AppShell alongside NavDrawerContext (declutter-invitation-board
// design.md Decision 2). The default is "expanded, no-op" so a sidebar
// rendered outside AppShell still works.
export const SidebarCollapseContext = createContext<SidebarCollapseContextValue>({
  isCollapsed: false,
  toggleCollapsed: () => {},
})

export function useSidebarCollapse(): SidebarCollapseContextValue {
  return useContext(SidebarCollapseContext)
}

export const SIDEBAR_COLLAPSED_STORAGE_KEY = 'vmss:ui:sidebar-collapsed'
