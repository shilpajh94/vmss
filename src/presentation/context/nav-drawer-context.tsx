import { createContext, useContext } from 'react'

interface NavDrawerContextValue {
  isNavOpen: boolean
  openNav: () => void
  closeNav: () => void
}

// Provided by AppShell. Lets each top bar render the menu button and each
// sidebar close the drawer on navigation, without either owning the state
// (make-web-pages-responsive's design.md Decision 2). The default value is a
// no-op so a sidebar rendered outside AppShell still works.
export const NavDrawerContext = createContext<NavDrawerContextValue>({
  isNavOpen: false,
  openNav: () => {},
  closeNav: () => {},
})

export function useNavDrawer(): NavDrawerContextValue {
  return useContext(NavDrawerContext)
}

export const NAV_DRAWER_ID = 'app-nav-drawer'
