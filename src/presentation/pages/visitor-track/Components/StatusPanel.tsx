import type { TrackingLookupResponse } from '../../../../domain/entities/tracking-lookup-response-schema'

// `submitted` is always done once there is a request to look up.
const TIMELINE_STAGES = [
  { value: 'submitted', label: 'Submitted' },
  { value: 'approved', label: 'Approved' },
  { value: 'checked-in', label: 'Checked In' },
  { value: 'checked-out', label: 'Checked Out' },
] as const

function currentStageIndex(stage: TrackingLookupResponse['timelineStage']): number {
  if (stage === 'complete') return TIMELINE_STAGES.length
  if (stage === 'unknown') return -1
  return TIMELINE_STAGES.findIndex((candidate) => candidate.value === stage)
}

const STATUS_TONE_CLASSES: Record<TrackingLookupResponse['statusTone'], string> = {
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  danger: 'bg-danger/10 text-danger',
  info: 'bg-info/10 text-info',
  neutral: 'bg-border-subtle text-text-muted',
}

interface StatusPanelProps {
  response: TrackingLookupResponse
}

export function StatusPanel({ response }: StatusPanelProps) {
  const currentIndex = currentStageIndex(response.timelineStage)

  return (
    <div className="flex w-full max-w-[480px] flex-col gap-4 rounded-2xl border border-border bg-surface p-5 shadow-[0_4px_8px_rgba(15,23,42,0.03)] md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-overline text-text-muted">Visitor Pass Specification</p>
          <p className="font-display text-[22px] font-bold text-text">ID: {response.trackingId}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-caption font-semibold ${STATUS_TONE_CLASSES[response.statusTone]}`}>
          {response.statusLabel}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 border-t sm:grid-cols-3 border-border-subtle pt-4">
        <div className="min-w-0">
          <p className="text-overline text-text-muted">Requested Date</p>
          <p className="truncate text-body text-text">{response.requestedDate}</p>
        </div>
        <div className="min-w-0">
          <p className="text-overline text-text-muted">Assigned Host</p>
          <p className="truncate text-body text-text" title={response.assignedHost}>
            {response.assignedHost}
          </p>
        </div>
        <div className="min-w-0">
          <p className="text-overline text-text-muted">Total Visitors</p>
          <p className="truncate text-body text-text">{response.totalVisitors} Registrants</p>
        </div>
      </div>

      <div className="flex flex-col gap-2 border-t border-border-subtle pt-4">
        <h4 className="text-body font-semibold text-text">Request Timeline Status</h4>
        <div className="flex items-center">
          {TIMELINE_STAGES.map((stage, index) => {
            const isComplete = currentIndex >= 0 ? index < currentIndex : index === 0
            const isCurrent = index === currentIndex
            const dotClass = isComplete ? 'bg-success' : isCurrent ? 'bg-warning' : 'border border-border bg-surface'

            return (
              <div key={stage.value} className="flex flex-1 items-center last:flex-none">
                <div className="flex flex-col items-center gap-1">
                  <span className={`size-3 rounded-full ${dotClass}`} />
                  <span className="whitespace-nowrap text-caption text-text-muted">{stage.label}</span>
                </div>
                {index < TIMELINE_STAGES.length - 1 && <span className="mx-1 h-px flex-1 bg-border" />}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
