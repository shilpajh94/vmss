import { AuthErrorAlert } from '../../components/auth/AuthFormParts'
import { SplitScreenLayout } from '../../components/layout/SplitScreenLayout'
import { VISITOR_BRAND, visitorFooterLinks } from '../../components/layout/visitor-brand'
import { CardSkeleton } from '../../components/ui/Skeleton'
import { StatusPanel } from './Components/StatusPanel'
import { TrackingLookupCard } from './Components/TrackingLookupCard'
import { useVisitorTrackLookup } from './hooks/use-visitor-track-lookup'

export function VisitorTrackPage() {
  const { trackingId, setTrackingId, validationError, status, response, errorMessage, submit } = useVisitorTrackLookup()

  return (
    // The result appears under the form, so once a lookup has run the
    // content starts at the top instead of re-centring as it grows.
    <SplitScreenLayout
      portalLabel="Visitor Portal"
      brand={VISITOR_BRAND}
      footerLinks={visitorFooterLinks()}
      back={{ to: '/' }}
      align={status === 'idle' ? 'center' : 'start'}
      contentClassName="max-w-[520px]"
    >
      <TrackingLookupCard
        trackingId={trackingId}
        onTrackingIdChange={setTrackingId}
        onSubmit={submit}
        loading={status === 'loading'}
        error={validationError}
      />
      {status === 'loading' && (
        <div role="status" aria-label="Looking up your request…" className="w-full">
          <CardSkeleton bodyClassName="h-32" />
        </div>
      )}
      {status === 'success' && response && <StatusPanel response={response} />}
      {status === 'error' && <AuthErrorAlert title="No Result" message={errorMessage ?? ''} />}
    </SplitScreenLayout>
  )
}
