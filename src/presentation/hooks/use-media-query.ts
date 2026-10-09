import { useSyncExternalStore } from 'react'

// Tailwind's default `lg` breakpoint — where the shell docks its sidebar and
// the invitation board shows every column side by side (see
// make-web-pages-responsive's design.md Decision 1).
export const DESKTOP_MEDIA_QUERY = '(min-width: 1024px)'
export const TABLET_MEDIA_QUERY = '(min-width: 768px)'

// Only for layouts whose render tree differs by breakpoint (design.md
// Decision 3); anything expressible in CSS uses Tailwind's `sm:`/`md:`/`lg:`
// variants instead, so it never re-renders on resize.
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mediaQueryList = window.matchMedia(query)
      mediaQueryList.addEventListener('change', onChange)
      return () => mediaQueryList.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    () => true,
  )
}

export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_MEDIA_QUERY)
}
