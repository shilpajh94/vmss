import type { VisitRequestFormState } from '../../types'

export type SubmissionStatus = 'idle' | 'submitting' | 'success' | 'error'

interface ReviewConfirmStepProps {
  formState: VisitRequestFormState
  status: SubmissionStatus
  trackingId?: string
  errorMessage?: string
  onBack: () => void
  onSubmit: () => void
}

function SummarySection({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface p-4">
      <h4 className="text-body font-semibold text-text">{title}</h4>
      <dl className="grid grid-cols-2 gap-2 text-body">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <dt className="text-caption text-text-muted">{label}</dt>
            <dd className="text-text">{value || '—'}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export function ReviewConfirmStep({ formState, status, trackingId, errorMessage, onBack, onSubmit }: ReviewConfirmStepProps) {
  if (status === 'success') {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-success bg-surface p-8 text-center">
        <h3 className="text-h3 text-text">Request Submitted</h3>
        <p className="text-body text-text-muted">Your visit request has been received. You can reference this tracking ID for any follow-up.</p>
        <p className="text-h2 text-primary">{trackingId}</p>
      </div>
    )
  }

  const visitors = [formState.primaryContact, ...formState.additionalVisitors]

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-h3 text-text">Review &amp; Confirm</h3>

      {status === 'error' && (
        <div className="rounded-lg border border-danger bg-surface p-4 text-body text-danger">
          {errorMessage ?? 'Something went wrong submitting your request. Please try again.'}
        </div>
      )}

      <SummarySection
        title={`Visitor Info (${formState.registrationType === 'group' ? `${visitors.length} visitors` : 'Individual'})`}
        rows={visitors.flatMap((visitor, index) => [
          [visitors.length > 1 ? `Visitor ${index + 1} Name` : 'Full Name', visitor.fullName],
          ['Email', visitor.email],
          ['Phone', visitor.phone],
          ['Address', visitor.address],
          ['Visitor Category', visitor.visitorCategory],
          ['ID Proof', visitor.idProofType],
          ['Profile Image', visitor.profileImageFileName ?? 'Not provided'],
        ] as [string, string][])}
      />

      <SummarySection
        title="Visit Info"
        rows={[
          ['Purpose', formState.visitInfo.purpose],
          ['Host', formState.visitInfo.hostNameOrEmail],
          ['Date', formState.visitInfo.preferredDate],
          ['Time', formState.visitInfo.preferredTime],
          ['Duration', formState.visitInfo.expectedDuration],
          ['Location', formState.visitInfo.location],
          ['Building', formState.visitInfo.building],
          ['Department', formState.visitInfo.department],
        ]}
      />

      <SummarySection
        title="Carried Items"
        rows={[
          ['Categories', formState.carriedItems.categories.join(', ') || 'None declared'],
          ['Description', formState.carriedItems.description],
        ]}
      />

      <SummarySection
        title="Vehicle Info"
        rows={
          formState.vehicles.length > 0
            ? formState.vehicles.map((vehicle, index) => [`Vehicle ${index + 1}`, `${vehicle.makeModel} · ${vehicle.licensePlate}`])
            : [['Vehicles', 'None declared']]
        }
      />

      <SummarySection
        title="Consent"
        rows={[
          ['Terms & Conditions', formState.consent.agreedTerms ? 'Agreed' : 'Not agreed'],
          ['Data Use', formState.consent.agreedDataUse ? 'Agreed' : 'Not agreed'],
          ['Safety Guidelines', formState.consent.agreedSafety ? 'Agreed' : 'Not agreed'],
        ]}
      />

      <div className="flex gap-3">
        <button type="button" onClick={onBack} disabled={status === 'submitting'} className="rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary">
          ← Back
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={status === 'submitting'}
          className="rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white disabled:opacity-60"
        >
          {status === 'submitting' ? 'Submitting…' : 'Submit Request'}
        </button>
      </div>
    </div>
  )
}
