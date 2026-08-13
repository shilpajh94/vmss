import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { StepSidebar } from './Components/StepSidebar'
import { CarriedItemsStep } from './Components/steps/CarriedItemsStep'
import { ConsentStep } from './Components/steps/ConsentStep'
import { ReviewConfirmStep } from './Components/steps/ReviewConfirmStep'
import { VehicleInfoStep } from './Components/steps/VehicleInfoStep'
import { VisitInfoStep } from './Components/steps/VisitInfoStep'
import { VisitorInfoStep } from './Components/steps/VisitorInfoStep'
import { useVisitorRequestWizard } from './hooks/use-visitor-request-wizard'

export function VisitorRequestPage() {
  const { currentStep, formState, setFormState, errors, goNext, goBack, uploadFile, submissionStatus, trackingId, submissionError, submit } =
    useVisitorRequestWizard()

  return (
    <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
      <PortalHeader backTo="/" />
      <div className="flex w-full flex-1 gap-8 px-12 py-10">
        <StepSidebar currentStep={currentStep} />
        <div className="flex-1 rounded-2xl border border-border bg-surface p-8">
          {currentStep === 0 && (
            <VisitorInfoStep
              registrationType={formState.registrationType}
              onRegistrationTypeChange={(registrationType) => setFormState({ ...formState, registrationType })}
              primaryContact={formState.primaryContact}
              onPrimaryContactChange={(primaryContact) => setFormState({ ...formState, primaryContact })}
              additionalVisitors={formState.additionalVisitors}
              onAdditionalVisitorsChange={(additionalVisitors) => setFormState({ ...formState, additionalVisitors })}
              uploadFile={uploadFile}
              errors={errors}
            />
          )}
          {currentStep === 1 && (
            <VisitInfoStep value={formState.visitInfo} onChange={(visitInfo) => setFormState({ ...formState, visitInfo })} errors={errors} />
          )}
          {currentStep === 2 && (
            <CarriedItemsStep value={formState.carriedItems} onChange={(carriedItems) => setFormState({ ...formState, carriedItems })} />
          )}
          {currentStep === 3 && (
            <VehicleInfoStep vehicles={formState.vehicles} onChange={(vehicles) => setFormState({ ...formState, vehicles })} errors={errors} />
          )}
          {currentStep === 4 && (
            <ConsentStep value={formState.consent} onChange={(consent) => setFormState({ ...formState, consent })} error={errors.consent} />
          )}
          {currentStep === 5 && (
            <ReviewConfirmStep
              formState={formState}
              status={submissionStatus}
              trackingId={trackingId}
              errorMessage={submissionError}
              onBack={goBack}
              onSubmit={submit}
            />
          )}

          {currentStep < 5 && (
            <div className="mt-8 flex justify-between">
              <button
                type="button"
                onClick={goBack}
                disabled={currentStep === 0}
                className="rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary disabled:opacity-0"
              >
                ← Back
              </button>
              <button type="button" onClick={goNext} className="rounded-lg bg-secondary-accent px-6 py-3 text-body font-semibold text-white">
                Next
              </button>
            </div>
          )}
        </div>
      </div>
      <PortalFooter />
    </div>
  )
}
