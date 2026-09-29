import { Outlet } from 'react-router'
import { RouteTransition } from './RouteTransition'

// Hosts the ungrouped, chrome-less routes (visitor portal, visitor request/track,
// admin/staff login) purely so they keep the same route-transition behavior as
// every other route now that RouteTransition no longer wraps the whole app.
export function PublicLayout() {
  return (
    <RouteTransition>
      <Outlet />
    </RouteTransition>
  )
}
