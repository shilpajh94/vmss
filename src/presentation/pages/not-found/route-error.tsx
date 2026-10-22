import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'

// The router's last-resort error page: a render error anywhere, or a page
// chunk that still fails after `lazyPage`'s one automatic reload. Rendered
// outside every provider, so it uses nothing but plain markup.
export function RouteErrorPage() {
  return (
    <div className="flex min-h-dvh w-full flex-col bg-bg">
      <PortalHeader />
      <main role="alert" className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-16 text-center">
        <h1 className="text-h1 text-text">Something went wrong</h1>
        <p className="max-w-md text-body text-text-muted">
          This page couldn't be loaded. Check your connection, then reload to try again.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="min-h-10 rounded-lg bg-primary px-6 py-3 text-body font-semibold text-on-primary transition-opacity hover:opacity-90"
        >
          Reload
        </button>
      </main>
      <PortalFooter />
    </div>
  )
}
