import heroImage from '../../../assets/images/lobby-hero.png'
import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { LoadingState } from '../../components/ui/LoadingState'
import { StatusPanel } from './Components/StatusPanel'
import { TrackingLookupCard } from './Components/TrackingLookupCard'
import { useVisitorTrackLookup } from './hooks/use-visitor-track-lookup'

export function VisitorTrackPage() {
  const { trackingId, setTrackingId, validationError, status, response, errorMessage, submit } = useVisitorTrackLookup()

  return (
    <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
      <PortalHeader backTo="/" />
      <div className="relative flex w-full flex-1 flex-col">
        <div aria-hidden className="absolute inset-0">
          <img src={heroImage} alt="" className="size-full object-cover" />
          <div className="absolute inset-0 bg-primary/55" />
        </div>
        <h1 className="text-h1 relative px-12 pt-10 pb-8 text-white">Track Your Visit</h1>
        <div className="relative flex flex-wrap justify-center gap-8 px-12 pb-16">
          <TrackingLookupCard
            trackingId={trackingId}
            onTrackingIdChange={setTrackingId}
            onSubmit={submit}
            loading={status === 'loading'}
            error={validationError}
          />
          {status === 'loading' && <LoadingState label="Looking up your request…" className="w-[480px]" />}
          {status === 'success' && response && <StatusPanel response={response} />}
          {status === 'error' && (
            <div className="flex w-[480px] flex-col gap-3 rounded-2xl border border-danger bg-surface p-8">
              <h3 className="text-h3 text-text">No Result</h3>
              <p className="text-body text-danger">{errorMessage}</p>
            </div>
          )}
        </div>
      </div>
      <PortalFooter />
    </div>
  )
}
