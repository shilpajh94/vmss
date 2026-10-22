import { Suspense } from 'react'
import { Outlet } from 'react-router'
import { RouteTransition } from './RouteTransition'
import { LoadingState } from './ui/LoadingState'
import { useApplyTheme } from '../context/theme-mode-context'

// Hosts the ungrouped, chrome-less routes (visitor portal, visitor request/track,
// admin/staff login) purely so they keep the same route-transition behavior as
// every other route now that RouteTransition no longer wraps the whole app.
// Always light, whatever the stored theme (theme-mode "Public pages always
// render in the light theme").
export function PublicLayout() {
  useApplyTheme('light')
  return (
    <RouteTransition>
      {/* The wizard, tracking and sign-in pages are chunks of their own. */}
      <Suspense fallback={<LoadingState label="Loading…" className="min-h-dvh bg-bg" />}>
        <Outlet />
      </Suspense>
    </RouteTransition>
  )
}
