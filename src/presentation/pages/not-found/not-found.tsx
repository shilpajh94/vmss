import { Link } from 'react-router'
import { AUTH_PRIMARY_BUTTON_CLASS, AuthFormHeading } from '../../components/auth/AuthFormParts'
import { SplitScreenLayout } from '../../components/layout/SplitScreenLayout'
import { VISITOR_BRAND, visitorFooterLinks } from '../../components/layout/visitor-brand'
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
    <SplitScreenLayout portalLabel="Visitor Portal" brand={VISITOR_BRAND} footerLinks={visitorFooterLinks()}>
      <div className="flex flex-col gap-3">
        <p className="font-display text-5xl font-bold text-text-faint">404</p>
        <AuthFormHeading
          title="Page not found"
          description="The page you were looking for doesn't exist or has moved. Check the address, or head back home."
        />
      </div>
      <Link to={home.to} className={AUTH_PRIMARY_BUTTON_CLASS}>
        {session.status === 'loading' ? 'Go home' : home.label}
      </Link>
    </SplitScreenLayout>
  )
}
