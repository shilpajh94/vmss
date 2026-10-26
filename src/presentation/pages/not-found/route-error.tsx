import { AUTH_PRIMARY_BUTTON_CLASS, AuthFormHeading } from '../../components/auth/AuthFormParts'
import { SplitScreenLayout } from '../../components/layout/SplitScreenLayout'
import { VISITOR_BRAND, visitorFooterLinks } from '../../components/layout/visitor-brand'
import { useForceLightTheme } from '../../context/theme-mode-context'

// The router's last-resort error page: a render error anywhere, or a page
// chunk that still fails after `lazyPage`'s one automatic reload. Rendered
// outside every provider, so it uses nothing but plain markup (the layout
// needs no router context without a `back`) — and, being outside
// PublicLayout too, forces the light theme itself.
export function RouteErrorPage() {
  useForceLightTheme()
  return (
    <SplitScreenLayout portalLabel="Visitor Portal" brand={VISITOR_BRAND} footerLinks={visitorFooterLinks()}>
      <div role="alert" className="flex flex-col gap-6">
        <AuthFormHeading
          title="Something went wrong"
          description="This page couldn't be loaded. Check your connection, then reload to try again."
        />
        <button type="button" onClick={() => window.location.reload()} className={`cursor-pointer ${AUTH_PRIMARY_BUTTON_CLASS}`}>
          Reload
        </button>
      </div>
    </SplitScreenLayout>
  )
}
