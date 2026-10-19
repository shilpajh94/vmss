import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'
import { NAV_DRAWER_ID, NavDrawerContext, useNavDrawer } from '../context/nav-drawer-context'
import { SIDEBAR_COLLAPSED_STORAGE_KEY, SidebarCollapseContext } from '../context/sidebar-collapse-context'
import { useFocusTrap } from '../hooks/use-focus-trap'
import { useIsDesktop } from '../hooks/use-media-query'
import { useStoredState } from '../hooks/use-stored-state'
import { MenuIcon } from './icons'
import { BrandLogo } from './BrandLogo'

function parseStoredBoolean(raw: unknown): boolean | undefined {
  return typeof raw === 'boolean' ? raw : undefined
}

interface AppShellProps {
  sidebar: ReactNode
  topBar?: ReactNode
  mainClassName?: string
  children: ReactNode
}

// The top-bar button that opens the off-canvas sidebar below `lg`. Hidden
// from `lg` up, where the sidebar is docked.
export function NavMenuButton({ className = '' }: { className?: string }) {
  const { isNavOpen, openNav } = useNavDrawer()
  return (
    <button
      type="button"
      onClick={openNav}
      aria-label="Open navigation menu"
      aria-expanded={isNavOpen}
      aria-controls={NAV_DRAWER_ID}
      className={`flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-text lg:hidden ${className}`}
    >
      <MenuIcon className="size-5" />
    </button>
  )
}

// Staff pages render their own headers as page content, so there's no shared
// top bar to hold the menu button — this phone/tablet-only bar stands in.
function MobileNavBar() {
  return (
    <div className="flex h-14 w-full shrink-0 items-center gap-3 border-b border-border bg-surface px-4 lg:hidden">
      <NavMenuButton />
      <BrandLogo variant="light" className="h-7" />
    </div>
  )
}

// Fixes the top bar in place and confines scrolling to the content region:
// `h-dvh` + `overflow-hidden` on the outer wrapper (not `min-h-screen`) caps
// the shell at the viewport so only `<main>` scrolls, vertically or
// horizontally. From `lg` up the sidebar is docked beside the content; below
// it the same sidebar element becomes an off-canvas drawer (app-shell
// "Sidebar collapses into a drawer below desktop width").
export function AppShell({ sidebar, topBar, mainClassName, children }: AppShellProps) {
  const location = useLocation()
  const isDesktop = useIsDesktop()
  const [isNavOpen, setIsNavOpen] = useState(false)
  const drawerRef = useRef<HTMLDivElement>(null)
  const [isRailPreferred, setIsRailPreferred] = useStoredState(SIDEBAR_COLLAPSED_STORAGE_KEY, false, parseStoredBoolean)

  const openNav = useCallback(() => setIsNavOpen(true), [])
  const closeNav = useCallback(() => setIsNavOpen(false), [])
  const drawerOpen = isNavOpen && !isDesktop

  // Belt-and-braces alongside each sidebar's own closeNav() on click: any
  // route change (back button, in-page link) closes the drawer too.
  useEffect(() => {
    setIsNavOpen(false)
  }, [location.pathname])

  // Widening past `lg` docks the sidebar; don't leave a stale open state
  // behind to reappear when the viewport shrinks again.
  useEffect(() => {
    if (isDesktop) setIsNavOpen(false)
  }, [isDesktop])

  useFocusTrap(drawerRef, drawerOpen, closeNav)

  const contextValue = useMemo(() => ({ isNavOpen: drawerOpen, openNav, closeNav }), [drawerOpen, openNav, closeNav])

  // The drawer below `lg` always shows the full sidebar; the stored rail
  // choice re-applies once the viewport is wide enough to dock it again.
  const toggleCollapsed = useCallback(() => setIsRailPreferred((previous) => !previous), [setIsRailPreferred])
  const collapseValue = useMemo(
    () => ({ isCollapsed: isRailPreferred && isDesktop, toggleCollapsed }),
    [isRailPreferred, isDesktop, toggleCollapsed],
  )

  return (
    <NavDrawerContext.Provider value={contextValue}>
      <SidebarCollapseContext.Provider value={collapseValue}>
        <div className={`flex h-dvh w-full items-stretch overflow-hidden bg-bg ${drawerOpen ? 'touch-none' : ''}`}>
          {/* Always mounted below `lg` so it can fade out as well as in
              (ui-motion "The navigation drawer slides in and out"); while
              closed it's transparent and lets clicks through. */}
          <button
            type="button"
            aria-label="Close navigation menu"
            aria-hidden={!drawerOpen || undefined}
            tabIndex={-1}
            onClick={closeNav}
            className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-standard ease-motion-out lg:hidden ${
              drawerOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
            }`}
          />

          <div
            ref={drawerRef}
            id={NAV_DRAWER_ID}
            role={isDesktop ? undefined : 'dialog'}
            aria-modal={drawerOpen || undefined}
            aria-label={isDesktop ? undefined : 'Navigation'}
            aria-hidden={!isDesktop && !drawerOpen ? true : undefined}
            inert={!isDesktop && !drawerOpen}
            className={`fixed inset-y-0 left-0 z-50 flex max-w-[85vw] transition-transform duration-standard ease-motion-out lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:transition-none ${
              drawerOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
            }`}
          >
            {sidebar}
          </div>

          <div className="flex h-dvh min-w-0 flex-1 flex-col overflow-hidden">
            {topBar ?? <MobileNavBar />}

            <main className={mainClassName ?? 'flex flex-1 flex-col gap-page-section overflow-y-auto overflow-x-hidden p-page-content [scrollbar-gutter:stable]'}>
              {children}
            </main>
          </div>
        </div>
      </SidebarCollapseContext.Provider>
    </NavDrawerContext.Provider>
  )
}
