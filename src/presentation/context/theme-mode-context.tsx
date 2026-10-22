import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useSyncExternalStore, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useStoredState } from '../hooks/use-stored-state'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

// Shared with the pre-paint script in index.html, which must read the same
// key before React loads (theme-mode "No flash of the wrong theme").
export const THEME_MODE_STORAGE_KEY = 'vmss.themeMode'
const DARK_QUERY = '(prefers-color-scheme: dark)'

function parseMode(raw: unknown): ThemeMode | undefined {
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : undefined
}

function subscribeToSystem(onChange: () => void): () => void {
  const query = window.matchMedia(DARK_QUERY)
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}

interface ThemeModeContextValue {
  mode: ThemeMode
  resolved: ResolvedTheme
  setMode: (mode: ThemeMode) => void
}

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null)

// Whether the current page shows the user's theme ('themed', the signed-in
// layouts) or is always light ('light', PublicLayout). Set by
// `useApplyTheme`, read when a switch is applied ahead of React.
let pageScope: 'themed' | 'light' = 'light'

function writeTheme(theme: ResolvedTheme): void {
  const root = document.documentElement
  if (theme === 'dark') root.dataset.theme = 'dark'
  else delete root.dataset.theme
}

// One clean repaint for a theme switch (theme-mode "Switching theme
// repaints in one clean step"; improve-calendar-scale-and-theme-switch
// design.md W4): colour transitions are suspended while the new tokens
// land (index.css `[data-theme-switching]`), then restored two frames
// later. `update` brings React state along in the same step.
function switchTheme(theme: ResolvedTheme, update: () => void, crossFade: boolean): void {
  const root = document.documentElement
  const apply = () => {
    root.setAttribute('data-theme-switching', '')
    writeTheme(theme)
    flushSync(update)
  }
  const finish = () => requestAnimationFrame(() => requestAnimationFrame(() => root.removeAttribute('data-theme-switching')))
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (crossFade && !reduceMotion && typeof document.startViewTransition === 'function') {
    // The callback runs after the old frame is captured; theme and state
    // change together inside it, so charts render with the new tokens.
    document.startViewTransition(apply).finished.finally(finish)
  } else {
    apply()
    finish()
  }
}

function resolve(mode: ThemeMode, systemIsDark: boolean): ResolvedTheme {
  return mode === 'system' ? (systemIsDark ? 'dark' : 'light') : mode
}

// The staff member's Light / Dark / System choice, stored per browser
// (add-calendar-colours-and-theme-modes design.md D4). Signed-in layouts
// apply it (`useApplyTheme`); public pages stay light whatever is stored.
export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, storeMode] = useStoredState<ThemeMode>(THEME_MODE_STORAGE_KEY, 'system', parseMode)
  const systemIsDark = useSyncExternalStore(
    subscribeToSystem,
    () => window.matchMedia(DARK_QUERY).matches,
    () => false,
  )
  const modeRef = useRef(mode)
  modeRef.current = mode

  const setMode = useCallback(
    (next: ThemeMode) => {
      const theme = resolve(next, window.matchMedia(DARK_QUERY).matches)
      if (pageScope === 'themed') switchTheme(theme, () => storeMode(next), true)
      else storeMode(next)
    },
    [storeMode],
  )

  // The device flipping while System is chosen: put the theme on <html>
  // in the event itself, before React's scheduled re-render reads it.
  useEffect(() => {
    const query = window.matchMedia(DARK_QUERY)
    const onChange = () => {
      if (modeRef.current === 'system' && pageScope === 'themed') {
        switchTheme(query.matches ? 'dark' : 'light', () => {}, false)
      }
    }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  // A choice made in another tab applies here too.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== THEME_MODE_STORAGE_KEY || event.newValue === null) return
      try {
        const next = parseMode(JSON.parse(event.newValue))
        if (next) setMode(next)
      } catch {
        // Ignore a malformed value written elsewhere.
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [setMode])

  const resolved = resolve(mode, systemIsDark)
  const value = useMemo(() => ({ mode, resolved, setMode }), [mode, resolved, setMode])
  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>
}

export function useThemeMode(): ThemeModeContextValue {
  const context = useContext(ThemeModeContext)
  if (!context) throw new Error('useThemeMode must be used within a ThemeModeProvider')
  return context
}

// Puts the theme on <html>. Signed-in layouts apply the user's resolved
// theme; PublicLayout passes 'light' so the visitor portal and the login
// pages never go dark. The same page-scope rule lives in the pre-paint
// script in index.html — change both together. A layout effect, so a route
// change between public and signed-in pages swaps it before paint; it also
// re-asserts the attribute from state after every switch, so a switch
// applied ahead of React can never drift from it.
export function useApplyTheme(force?: ResolvedTheme): void {
  const { resolved } = useThemeMode()
  const theme = force ?? resolved
  useLayoutEffect(() => {
    pageScope = force ? 'light' : 'themed'
    writeTheme(theme)
  }, [theme, force])
}
