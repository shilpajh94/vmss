import { useCallback, useEffect, useState } from 'react'
import { PreferredContactMethodSchema } from '../../../domain/entities/preferred-contact-method'
import { FormSkeleton, Skeleton } from '../../components/ui/Skeleton'
import { GroupErrorsContext } from '../../components/dynamic-fields/group-errors-context'
import { useNavigate } from 'react-router'
import { SplitScreenLayout } from '../../components/layout/SplitScreenLayout'
import { VISITOR_BRAND, visitorFooterLinks } from '../../components/layout/visitor-brand'
import { StepProgressHeader } from './Components/StepProgressHeader'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { VisitorPortalMe } from '../../../domain/entities/visitor-portal-schema'
import { ReturnVisitHistoryScreen } from './Components/history/ReturnVisitHistoryScreen'
import { OtpRequestScreen } from './Components/otp/OtpRequestScreen'
import { OtpScreenLayout } from './Components/otp/OtpScreenLayout'
import { OtpVerifyScreen } from './Components/otp/OtpVerifyScreen'
import { StepSidebar } from './Components/StepSidebar'
import { useStepDirection } from '../../hooks/use-step-direction'
import { useUnsavedChangesGuard } from '../../hooks/use-unsaved-changes-guard'
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
    hasUnsavedInput,
    trackingId,
    confirmedFullName,
    submissionError,
    submit,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
    carriedItemsCustomFields,
    carriedItemsGroups,
    carriedItemsAllFields,
    consentFields,
    visitorInfoFields,
    purposeOfVisitOptions,
    vehicleInfoFields,
    visitorInfoCustomFields,
    visitorInfoGroups,
    visitorInfoAllFields,
    visitDetailsCustomFields,
    vehicleInfoCustomFields,
    primaryContactNameLocked,
    vehicleInfoGroups,
    vehicleInfoAllFields,
  } = useVisitorRequestWizard(initial, branches, buildings)

  useUnsavedChangesGuard(hasUnsavedInput)

  const stepLabels = isFormConfigLoading ? getSkeletonStepLabels() : activeSteps.map(resolveStepLabel)
  const activeStep = activeSteps[currentStep]
  const stepDirection = useStepDirection(currentStep)

  // Also used as the retry action from the Visitor Category field's error
  // state — re-running it resets status to 'loading' first.
  const loadVisitorCategories = useCallback(async () => {
    setVisitorCategoriesState((previous) => ({ status: 'loading', categories: previous.categories }))
    try {
      const categories = await listVisitorCategoriesUseCase.execute({ activeOnly: true })
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
    <GroupErrorsContext.Provider value={errors}>
      {/* `navigate` goes through the router, so the unsaved-changes guard
          still intercepts the panel's Back. The navy panel carries the step
          list instead of the brand copy, and no photo (design D4). */}
      <SplitScreenLayout
        portalLabel="Visitor Portal"
        brand={VISITOR_BRAND}
        footerLinks={visitorFooterLinks()}
        back={{ onClick: () => navigate('/') }}
        panel={<StepSidebar steps={stepLabels} currentStep={currentStep} onStepSelect={goToStep} />}
        panelClassName="w-[340px]"
        align="start"
        showPortalTag={false}
        contentClassName="max-w-[760px]"
      >
        <StepProgressHeader steps={stepLabels} currentStep={currentStep} onStepSelect={goToStep} />
        <div className="min-w-0 overflow-x-clip">
          {/* The action bar below stays outside this keyed wrapper, so only the step content slides. */}
          <div key={currentStep} data-direction={stepDirection} className="step-enter">
            {isFormConfigLoading && <FormSkeleton bare rows={3} label="Loading the registration form…" />}

            {!isFormConfigLoading && formConfigError && (
              <p className="text-body text-danger">Something went wrong loading the registration form. Please refresh the page.</p>
            )}

            {!isFormConfigLoading && !formConfigError && activeStep?.key === 'visitor_info' && (
              <VisitorInfoStep
                registrationType={formState.registrationType}
                onRegistrationTypeChange={(registrationType) => setFormState({ ...formState, registrationType })}
                primaryContact={formState.primaryContact}
                onPrimaryContactChange={(primaryContact) => setFormState({ ...formState, primaryContact })}
                primaryContactNameLocked={primaryContactNameLocked}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
                errors={errors}
                visitorCategoriesState={visitorCategoriesState}
                onRetryVisitorCategories={loadVisitorCategories}
                visitorInfoFields={visitorInfoFields}
                customFields={visitorInfoCustomFields}
                groups={visitorInfoGroups}
                groupFields={visitorInfoAllFields}
                groupValues={formState.groupValues}
                onGroupValuesChange={(groupValues) => setFormState({ ...formState, groupValues })}
              />
            )}
            {!isFormConfigLoading && !formConfigError && activeStep?.key === 'visit_details' && (
              <VisitInfoStep
                value={formState.visitInfo}
                onChange={(visitInfo) => setFormState({ ...formState, visitInfo })}
                errors={errors}
                branches={branches}
                buildings={buildings}
                purposeOfVisitOptions={purposeOfVisitOptions}
                customFields={visitDetailsCustomFields}
                customFieldValues={formState.customFieldValues}
                onCustomFieldValuesChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
              />
            )}
            {!isFormConfigLoading && !formConfigError && activeStep?.key === 'carried_items' && (
              <CarriedItemsStep
                fields={carriedItemsFields}
                isLoading={false}
                value={formState.carriedItems}
                onChange={(carriedItems) => setFormState({ ...formState, carriedItems })}
                customFields={carriedItemsCustomFields}
                customFieldValues={formState.customFieldValues}
                onCustomFieldValuesChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
                groups={carriedItemsGroups}
                groupFields={carriedItemsAllFields}
                groupValues={formState.groupValues}
                onGroupValuesChange={(groupValues) => setFormState({ ...formState, groupValues })}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
              />
            )}
            {!isFormConfigLoading && !formConfigError && activeStep?.key === 'vehicle_info' && (
              <VehicleInfoStep
                vehicles={formState.vehicles}
                onChange={(vehicles) => setFormState({ ...formState, vehicles })}
                errors={errors}
                vehicleInfoFields={vehicleInfoFields}
                customFields={vehicleInfoCustomFields}
                groups={vehicleInfoGroups}
                groupFields={vehicleInfoAllFields}
                groupValues={formState.groupValues}
                onGroupValuesChange={(groupValues) => setFormState({ ...formState, groupValues })}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
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
                confirmedFullName={confirmedFullName}
                errorMessage={submissionError}
                visitorCategories={visitorCategoriesState.categories}
                getFilePreviewUrl={getFilePreviewUrl}
                vehicleCustomFields={vehicleInfoCustomFields}
                carriedItemsCustomFields={carriedItemsCustomFields}
                visitorInfoGroups={visitorInfoGroups}
                visitorInfoAllFields={visitorInfoAllFields}
                vehicleInfoGroups={vehicleInfoGroups}
                vehicleInfoAllFields={vehicleInfoAllFields}
                carriedItemsGroups={carriedItemsGroups}
                carriedItemsAllFields={carriedItemsAllFields}
                visitorInfoCustomFields={visitorInfoCustomFields}
                visitDetailsCustomFields={visitDetailsCustomFields}
                steps={activeSteps}
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
                groupValues={formState.groupValues}
                onGroupValuesChange={(groupValues) => setFormState({ ...formState, groupValues })}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
              />
            )}
          </div>

          {!isFormConfigLoading && !formConfigError && activeStep?.key !== 'review_confirm' && (
            // Pinned to the bottom of the scrolling content panel at every
            // width, so Back/Next stay reachable while a long step scrolls.
            <div className="sticky bottom-0 z-10 mt-8 flex justify-between gap-3 border-t border-border-subtle bg-surface py-4">
              <button
                type="button"
                onClick={goBack}
                disabled={currentStep === 0}
                title="Go back to the previous step"
                className="cursor-pointer rounded-lg border border-border px-6 py-3 text-body font-semibold text-text transition-colors enabled:hover:bg-border-subtle disabled:cursor-not-allowed disabled:opacity-0"
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={goNext}
                title="Continue to the next step"
                className="relative cursor-pointer rounded-lg bg-secondary-accent px-6 py-3 text-body font-semibold text-white shadow-[0_8px_20px_-6px_rgba(6,182,212,0.55)] after:absolute after:inset-x-0 after:top-full after:h-0.5 transition-[transform,box-shadow] duration-[var(--motion-fast)] hover:-translate-y-px hover:shadow-[0_12px_24px_-6px_rgba(6,182,212,0.6)]"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </SplitScreenLayout>
    </GroupErrorsContext.Provider>
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

  const preferredContactMethod = PreferredContactMethodSchema.safeParse(prefill.preferredContactMethod).data

  return {
    ...base,
    fullName: prefill.fullName,
    email: prefill.email ?? base.email,
    phone: prefill.phone ?? base.phone,
    preferredContactMethod,
    idProofType: prefill.idProofType ?? undefined,
    idProofUrl: prefill.idProofUrl ?? undefined,
    photoUrl: prefill.photoUrl ?? undefined,
    visitorCategory: prefill.visitorCategoryId ?? undefined,
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
    return <VisitorRequestWizard initial={wizardInitial} />
  }

  // A verified visitor with prior visits (or a retryable lookup error) sees
  // the history screen instead of jumping straight to the wizard. Loading
  // the initial page, or a first-time visitor's empty result, falls through
  // to the plain spinner below rather than ever mounting this screen.
  const hasHistoryToShow = portal.status === 'loaded' && (portal.data?.history.length ?? 0) > 0
  const hasRetryableError = portal.status === 'rate-limited' || portal.status === 'misconfigured' || portal.status === 'error'

  if (hasHistoryToShow || hasRetryableError) {
    return (
      <OtpScreenLayout onBack={() => navigate('/')} align="start" contentClassName="max-w-[560px]">
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
    )
  }

  const isLookingUpHistory = portal.status === 'loading'

  return (
    <OtpScreenLayout onBack={() => navigate('/')}>
      {isLookingUpHistory ? (
        <div role="status" aria-label="Looking up your visits…" className="flex w-full flex-col gap-3">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-2/3" />
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
  )
}
