import { Link } from 'react-router'
import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { useStaffSession } from '../../components/session/use-staff-session'
import { landingPathFor } from '../../utils/landing-path'

// Any path no route matches (app-shell "An Unknown Route Shows a Not-Found
// Page"), instead of a blank screen. A signed-in user's link goes to their
// own dashboard; everyone else's to the visitor portal.
export function NotFoundPage() {
  const { session } = useStaffSession()
  const home =
    session.status === 'ready'
      ? { to: landingPathFor(session.user), label: 'Go to your dashboard' }
      : { to: '/', label: 'Go to the visitor portal' }

  return (
    <div className="flex min-h-dvh w-full flex-col bg-bg">
      <PortalHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-16 text-center">
        <p className="font-display text-5xl font-bold text-text-faint">404</p>
        <h1 className="text-h1 text-text">Page not found</h1>
        <p className="max-w-md text-body text-text-muted">The page you were looking for doesn't exist or has moved. Check the address, or head back home.</p>
        <Link
          to={home.to}
          className="min-h-10 rounded-lg bg-primary px-6 py-3 text-body font-semibold text-on-primary transition-opacity hover:opacity-90"
        >
          {session.status === 'loading' ? 'Go home' : home.label}
        </Link>
      </main>
      <PortalFooter />
    </div>
  )
}
