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
export function RouteTransition({ children }: RouteTransitionProps) {
  const location = useLocation()

  return (
    <div key={location.pathname} className="route-transition">
      {children}
    </div>
  )
}
