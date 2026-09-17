import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { useAppDependencies } from '../../context/app-dependencies-context'
import { Spinner } from '../../components/ui/LoadingState'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { VisitorPortalMe } from '../../../domain/entities/visitor-portal-schema'
import { ReturnVisitHistoryScreen } from './Components/history/ReturnVisitHistoryScreen'
import { OtpRequestScreen } from './Components/otp/OtpRequestScreen'
import { OtpScreenLayout } from './Components/otp/OtpScreenLayout'
import { OtpVerifyScreen } from './Components/otp/OtpVerifyScreen'
import { StepSidebar } from './Components/StepSidebar'
import { CarriedItemsStep } from './Components/steps/CarriedItemsStep'
import { ConsentStep } from './Components/steps/ConsentStep'
import { GenericConfiguredStep } from './Components/steps/GenericConfiguredStep'
import { ReviewConfirmStep } from './Components/steps/ReviewConfirmStep'
import { VehicleInfoStep } from './Components/steps/VehicleInfoStep'
import { VisitInfoStep } from './Components/steps/VisitInfoStep'
import { VisitorInfoStep } from './Components/steps/VisitorInfoStep'
import { useReturningVisitorPortal } from './hooks/use-returning-visitor-portal'
import { useVisitorOtp } from './hooks/use-visitor-otp'
import { useVisitorRequestWizard, type VisitorRequestWizardInitialData } from './hooks/use-visitor-request-wizard'
import { getSkeletonStepLabels, isCanonicalStepKey, resolveStepLabel } from './registration-wizard-steps'
import type { RegistrationType, VisitorCategoriesFieldState } from './types'

function VisitorRequestWizard({ initial }: { initial?: VisitorRequestWizardInitialData }) {
  const navigate = useNavigate()
  const { listVisitorCategoriesUseCase, listBranchesUseCase, listBuildingsUseCase } = useAppDependencies()
  const [visitorCategoriesState, setVisitorCategoriesState] = useState<VisitorCategoriesFieldState>({
    status: 'loading',
    categories: [],
  })
  const [branches, setBranches] = useState<Branch[] | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[] | undefined>(undefined)

  const {
    currentStep,
    formState,
    setFormState,
    errors,
    goNext,
    goBack,
    goToStep,
    uploadFile,
    getFilePreviewUrl,
    submissionStatus,
    trackingId,
    submissionError,
    submit,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
    consentFields,
    visitorInfoFields,
    additionalNotesActive,
    vehicleInfoFields,
    visitorInfoCustomFields,
    visitDetailsCustomFields,
    vehicleInfoCustomFields,
  } = useVisitorRequestWizard(initial, branches)

  const stepLabels = isFormConfigLoading ? getSkeletonStepLabels() : activeSteps.map(resolveStepLabel)
  const activeStep = activeSteps[currentStep]

  // Also used as the retry action from the Visitor Category field's error
  // state — re-running it resets status to 'loading' first.
  const loadVisitorCategories = useCallback(async () => {
    setVisitorCategoriesState((previous) => ({ status: 'loading', categories: previous.categories }))
    try {
      const categories = await listVisitorCategoriesUseCase.execute()
      setVisitorCategoriesState({ status: 'loaded', categories })
    } catch (error) {
      console.error('Failed to load visitor categories', error)
      setVisitorCategoriesState({ status: 'error', categories: [] })
    }
  }, [listVisitorCategoriesUseCase])

  // Each call is caught independently — a Promise.all would let one rejection
  // block every field's data.
  const loadVisitInfoMasterData = useCallback(() => {
    listBranchesUseCase
      .execute()
      .then(setBranches)
      .catch(() => {
        // Falls back to a free-text Location field.
      })
    listBuildingsUseCase
      .execute()
      .then(setBuildings)
      .catch(() => {
        // Falls back to a free-text Building field.
      })
  }, [listBranchesUseCase, listBuildingsUseCase])

  useEffect(() => {
    void loadVisitorCategories()
    loadVisitInfoMasterData()
  }, [loadVisitorCategories, loadVisitInfoMasterData])

  return (
    <div className="flex w-full flex-1 gap-8 px-12 py-10">
      <StepSidebar steps={stepLabels} currentStep={currentStep} onStepSelect={goToStep} />
      <div className="flex-1 rounded-2xl border border-border bg-surface p-8">
        {isFormConfigLoading && <p className="text-body text-text-muted">Loading…</p>}

        {!isFormConfigLoading && formConfigError && (
          <p className="text-body text-danger">Something went wrong loading the registration form. Please refresh the page.</p>
        )}

        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'visitor_info' && (
          <VisitorInfoStep
            registrationType={formState.registrationType}
            onRegistrationTypeChange={(registrationType) => setFormState({ ...formState, registrationType })}
            primaryContact={formState.primaryContact}
            onPrimaryContactChange={(primaryContact) => setFormState({ ...formState, primaryContact })}
            additionalVisitors={formState.additionalVisitors}
            onAdditionalVisitorsChange={(additionalVisitors) => setFormState({ ...formState, additionalVisitors })}
            uploadFile={uploadFile}
            getFilePreviewUrl={getFilePreviewUrl}
            errors={errors}
            visitorCategoriesState={visitorCategoriesState}
            onRetryVisitorCategories={loadVisitorCategories}
            visitorInfoFields={visitorInfoFields}
            customFields={visitorInfoCustomFields}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'visit_details' && (
          <VisitInfoStep
            value={formState.visitInfo}
            onChange={(visitInfo) => setFormState({ ...formState, visitInfo })}
            errors={errors}
            branches={branches}
            buildings={buildings}
            additionalNotesActive={additionalNotesActive}
            customFields={visitDetailsCustomFields}
            customFieldValues={formState.customFieldValues}
            onCustomFieldValuesChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'carried_items' && (
          <CarriedItemsStep
            fields={carriedItemsFields}
            isLoading={false}
            value={formState.carriedItems}
            onChange={(carriedItems) => setFormState({ ...formState, carriedItems })}
            customFieldValues={formState.customFieldValues}
            onCustomFieldValuesChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'vehicle_info' && (
          <VehicleInfoStep
            vehicles={formState.vehicles}
            onChange={(vehicles) => setFormState({ ...formState, vehicles })}
            errors={errors}
            vehicleInfoFields={vehicleInfoFields}
            customFields={vehicleInfoCustomFields}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'consent_agreement' && (
          <ConsentStep
            fields={consentFields}
            isLoading={false}
            value={formState.consent}
            onChange={(consent) => setFormState({ ...formState, consent })}
            error={errors.consent}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep?.key === 'review_confirm' && (
          <ReviewConfirmStep
            formState={formState}
            status={submissionStatus}
            trackingId={trackingId}
            errorMessage={submissionError}
            visitorCategories={visitorCategoriesState.categories}
            getFilePreviewUrl={getFilePreviewUrl}
            vehicleCustomFields={vehicleInfoCustomFields}
            carriedItemsCustomFields={carriedItemsFields.filter((field) => !field.isSystem)}
            onBack={goBack}
            onSubmit={submit}
            onGoHome={() => navigate('/')}
          />
        )}
        {!isFormConfigLoading && !formConfigError && activeStep && !isCanonicalStepKey(activeStep.key) && (
          <GenericConfiguredStep
            step={activeStep}
            value={formState.customFieldValues}
            onChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
          />
        )}

        {!isFormConfigLoading && !formConfigError && activeStep?.key !== 'review_confirm' && (
          <div className="mt-8 flex justify-between">
            <button
              type="button"
              onClick={goBack}
              disabled={currentStep === 0}
              title="Go back to the previous step"
              className="cursor-pointer rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary transition-colors enabled:hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-0"
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={goNext}
              title="Continue to the next step"
              className="cursor-pointer rounded-lg bg-secondary-accent px-6 py-3 text-body font-semibold text-white transition-colors hover:opacity-90"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// Builds the wizard's primary-contact prefill from the verified contact plus,
// when available, the returning visitor's known profile (visitor-return-history).
// idProofUrl/photoUrl, when present, are carried through so the wizard can
// offer to reuse them (allow-returning-visitor-photo-id-reuse) instead of
// always requiring a fresh upload.
function buildPrimaryContactPrefill(
  contact: string,
  prefill: VisitorPortalMe['prefill'],
): VisitorRequestWizardInitialData['primaryContact'] {
  const base = contact.includes('@') ? { email: contact } : { phone: contact }
  if (!prefill) return base

  const preferredContactMethod = prefill.preferredContactMethod === 'email' || prefill.preferredContactMethod === 'sms'
    ? prefill.preferredContactMethod
    : undefined

  return {
    ...base,
    fullName: prefill.fullName,
    email: prefill.email ?? base.email,
    phone: prefill.phone ?? base.phone,
    preferredContactMethod,
    idProofType: prefill.idProofType ?? undefined,
    idProofUrl: prefill.idProofUrl ?? undefined,
    photoUrl: prefill.photoUrl ?? undefined,
  }
}

export function VisitorRequestPage() {
  const navigate = useNavigate()
  const [wizardInitial, setWizardInitial] = useState<VisitorRequestWizardInitialData | undefined>(undefined)
  const [pending, setPending] = useState<{ registrationType: RegistrationType; contact: string } | undefined>(undefined)

  const portal = useReturningVisitorPortal()

  const otp = useVisitorOtp({
    onVerified: (registrationType, contact, proofToken) => {
      setPending({ registrationType, contact })
      portal.load(proofToken)
    },
  })

  // 401 from the lookup: the proof token expired/was invalid — return to the
  // OTP-request screen to get a fresh code (visitor-otp-verification's
  // "History lookup rejects the proof token" scenario).
  useEffect(() => {
    if (portal.status === 'unauthorized') {
      setPending(undefined)
      otp.useDifferentContact()
    }
  }, [portal.status, otp])

  // First-time visitor (no history, null prefill): skip the history screen
  // and go straight into the wizard, exactly as before this feature.
  useEffect(() => {
    if (portal.status === 'loaded' && portal.data && portal.data.history.length === 0 && pending) {
      setWizardInitial({
        registrationType: pending.registrationType,
        primaryContact: buildPrimaryContactPrefill(pending.contact, portal.data.prefill),
      })
    }
  }, [portal.status, portal.data, pending])

  const startNewRequestFromHistory = () => {
    if (!pending) return
    setWizardInitial({
      registrationType: pending.registrationType,
      primaryContact: buildPrimaryContactPrefill(pending.contact, portal.data?.prefill ?? null),
    })
  }

  if (wizardInitial) {
    return (
      <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
        <PortalHeader backTo="/" />
        <VisitorRequestWizard initial={wizardInitial} />
        <PortalFooter />
      </div>
    )
  }

  // A verified visitor with prior visits (or a retryable lookup error) sees
  // the history screen instead of jumping straight to the wizard. Loading
  // the initial page, or a first-time visitor's empty result, falls through
  // to the plain spinner below rather than ever mounting this screen.
  const hasHistoryToShow = portal.status === 'loaded' && (portal.data?.history.length ?? 0) > 0
  const hasRetryableError = portal.status === 'rate-limited' || portal.status === 'misconfigured' || portal.status === 'error'

  if (hasHistoryToShow || hasRetryableError) {
    return (
      <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
        <PortalHeader />
        <OtpScreenLayout onBack={() => navigate('/')}>
          <ReturnVisitHistoryScreen
            status={portal.status}
            history={portal.data?.history ?? []}
            errorMessage={portal.errorMessage}
            hasMore={portal.hasMore}
            onLoadMore={portal.loadMore}
            onRetry={portal.retry}
            onStartNewRequest={startNewRequestFromHistory}
          />
        </OtpScreenLayout>
        <PortalFooter />
      </div>
    )
  }

  const isLookingUpHistory = portal.status === 'loading'

  return (
    <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
      <PortalHeader />
      <OtpScreenLayout onBack={() => navigate('/')}>
        {isLookingUpHistory ? (
          <div className="flex h-fit w-[480px] items-center justify-center gap-2 rounded-2xl border border-border bg-surface p-8 text-body text-text-muted shadow-[0_4px_8px_rgba(15,23,42,0.03)]">
            <Spinner className="size-4 border-border border-t-secondary-accent" />
            Looking up your visits…
          </div>
        ) : otp.phase === 'request' ? (
          <OtpRequestScreen
            registrationType={otp.registrationType}
            onRegistrationTypeChange={otp.setRegistrationType}
            contact={otp.contact}
            onContactChange={otp.setContact}
            contactError={otp.contactError}
            requestErrorMessage={otp.requestErrorMessage}
            loading={otp.requestStatus === 'requesting'}
            onSubmit={otp.requestOtp}
          />
        ) : (
          <OtpVerifyScreen
            code={otp.code}
            onCodeChange={otp.setCode}
            codeError={otp.codeError}
            verifyErrorMessage={otp.verifyErrorMessage}
            loading={otp.verifyStatus === 'verifying'}
            onSubmit={otp.verifyOtp}
            onUseDifferentContact={otp.useDifferentContact}
          />
        )}
      </OtpScreenLayout>
      <PortalFooter />
    </div>
  )
}
