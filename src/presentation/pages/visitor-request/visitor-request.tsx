import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
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
import { useVisitorOtp } from './hooks/use-visitor-otp'
import { useVisitorRequestWizard, type VisitorRequestWizardInitialData } from './hooks/use-visitor-request-wizard'
import { getSkeletonStepLabels, isCanonicalStepKey, resolveStepLabel } from './registration-wizard-steps'
import type { VisitorCategoriesFieldState } from './types'

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
    vehicleInfoGroups,
    vehicleInfoAllFields,
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

export function VisitorRequestPage() {
  const navigate = useNavigate()
  const [wizardInitial, setWizardInitial] = useState<VisitorRequestWizardInitialData | undefined>(undefined)

  const otp = useVisitorOtp({
    onVerified: (registrationType, contact) => {
      const primaryContact = contact.includes('@') ? { email: contact } : { phone: contact }
      setWizardInitial({ registrationType, primaryContact })
    },
  })

  if (wizardInitial) {
    return (
      <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
        <PortalHeader backTo="/" />
        <VisitorRequestWizard initial={wizardInitial} />
        <PortalFooter />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen w-full flex-col bg-[#f8fafc]">
      <PortalHeader />
      <OtpScreenLayout onBack={() => navigate('/')}>
        {otp.phase === 'request' ? (
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
