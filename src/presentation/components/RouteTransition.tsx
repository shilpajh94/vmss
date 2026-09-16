import type { ReactNode } from 'react'
import { useLocation } from 'react-router'

interface RouteTransitionProps {
  children: ReactNode
}

// Plays a brief fade/slide-in on route change instead of an instant
// content swap. Keying the wrapper on the pathname forces React to remount
// it on every navigation, which restarts the CSS animation defined for
// `.route-transition` in index.css (that stylesheet also disables it under
// `prefers-reduced-motion: reduce`). CSS-only by design — no animation
// library — so only the entering view animates; there is no exit animation.
//
// `flex h-full min-h-0 flex-col` makes this wrapper stretch to fill
// <main>'s available height (which is itself a definite, not auto, height -
// see AppShell.tsx) instead of sizing to its content. A page that renders
// short content just leaves empty space below it, same as before. A page
// that renders tall content and does NOT opt into PageContentLayout still
// overflows this box normally, so <main>'s own overflow-y-auto keeps
// scrolling it exactly as before. A page that DOES use PageContentLayout
// gets a data region that scrolls internally instead, since it never
// exceeds this wrapper's height in the first place.
export function RouteTransition({ children }: RouteTransitionProps) {
  const location = useLocation()

  return (
    <div key={location.pathname} className="route-transition flex h-full min-h-0 flex-col">
      {children}
    </div>
  )
}
