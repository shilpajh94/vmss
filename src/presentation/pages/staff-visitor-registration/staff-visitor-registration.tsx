import { useCallback, useEffect, useRef, useState } from 'react'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { GroupErrorsContext } from '../../components/dynamic-fields/group-errors-context'
import { useNavigate } from 'react-router'
import { PageContentLayout } from '../../components/PageContentLayout'
import { useAppDependencies } from '../../context/app-dependencies-context'
import { usePageHeader } from '../../context/page-header-context'
import { useIsDesktop } from '../../hooks/use-media-query'
import { useStepDirection } from '../../hooks/use-step-direction'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { VisitorCategory } from '../../../domain/entities/visitor-category-schema'
import { CarriedItemsStep } from '../visitor-request/Components/steps/CarriedItemsStep'
import { ConsentStep } from '../visitor-request/Components/steps/ConsentStep'
import { GenericConfiguredStep } from '../visitor-request/Components/steps/GenericConfiguredStep'
import { ReviewConfirmStep } from '../visitor-request/Components/steps/ReviewConfirmStep'
import { VehicleInfoStep } from '../visitor-request/Components/steps/VehicleInfoStep'
import { VisitInfoStep } from '../visitor-request/Components/steps/VisitInfoStep'
import { getSkeletonStepLabels, isCanonicalStepKey, resolveStepLabel } from '../visitor-request/registration-wizard-steps'
import { RegistrationStepper } from './Components/RegistrationStepper'
import { RegistrationWorkspaceHeader } from './Components/RegistrationWorkspaceHeader'
import { VisitorInfoStep } from './Components/VisitorInfoStep'
import { useStaffVisitorRegistrationWizard } from './hooks/use-staff-visitor-registration-wizard'
import { createInitialStaffFormState } from './types'
import { useFormPageRefresh } from '../../hooks/use-form-page-refresh'

export function StaffVisitorRegistrationPage() {
  const navigate = useNavigate()
  const { listBranchesUseCase, listBuildingsUseCase, listVisitorCategoriesUseCase } = useAppDependencies()
  const [branches, setBranches] = useState<Branch[] | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[] | undefined>(undefined)
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[] | undefined>(undefined)
  const [isMasterDataLoading, setIsMasterDataLoading] = useState(true)

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
    confirmedFullName,
    submissionError,
    submit,
    reset,
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
  } = useStaffVisitorRegistrationWizard(branches, buildings)

  usePageHeader({ description: 'Pre-register visitors for your organization' })

  const stepDirection = useStepDirection(currentStep)
  const stepLabels = isFormConfigLoading ? getSkeletonStepLabels() : activeSteps.map(resolveStepLabel)
  const activeStep = activeSteps[currentStep]
  const nextStepLabel = activeSteps[currentStep + 1] ? resolveStepLabel(activeSteps[currentStep + 1]) : undefined

  // A new step should open at its top, not wherever the previous step was
  // scrolled to. From `lg` up the form region is its own scroller; below
  // that the whole page (AppShell's <main>) scrolls, so bring the page top
  // back into view instead. Skipped on mount so landing on the page doesn't jump.
  const isDesktop = useIsDesktop()
  const rootRef = useRef<HTMLDivElement>(null)
  const formRegionRef = useRef<HTMLDivElement>(null)
  const previousStepRef = useRef(currentStep)
  useEffect(() => {
    if (previousStepRef.current === currentStep) return
    previousStepRef.current = currentStep
    if (isDesktop) formRegionRef.current?.scrollTo({ top: 0 })
    else rootRef.current?.scrollIntoView({ block: 'start' })
  }, [currentStep, isDesktop])

  const loadVisitInfoMasterData = useCallback(async () => {
    setIsMasterDataLoading(true)
    try {
      const [branchList, buildingList, categoryList] = await Promise.all([
        listBranchesUseCase.execute({ activeOnly: true }),
        listBuildingsUseCase.execute({ activeOnly: true }),
        listVisitorCategoriesUseCase.execute({ activeOnly: true }),
      ])
      setBranches(branchList)
      setBuildings(buildingList)
      setVisitorCategories(categoryList)
    } catch (error) {
      // Visit Info step falls back to free-text fields if master data can't be loaded.
      console.error('Failed to load visit info master data', error)
    } finally {
      setIsMasterDataLoading(false)
    }
  }, [listBranchesUseCase, listBuildingsUseCase, listVisitorCategoriesUseCase])

  useEffect(() => {
    void loadVisitInfoMasterData()
  }, [loadVisitInfoMasterData])

  // The top-bar refresh starts the registration over from step 1 with fresh
  // master data; it asks first once anything has been entered.
  // `reset` is recreated every render; reading it through a ref keeps this
  // callback stable so the refresh registration doesn't churn.
  const resetRef = useRef(reset)
  resetRef.current = reset
  const reloadRegistration = useCallback(() => {
    resetRef.current()
    void loadVisitInfoMasterData()
  }, [loadVisitInfoMasterData])

  // The baseline is the empty form: the wizard can be typed into while its
  // option lists load. A submitted registration has nothing left unsaved.
  const [initialFormState] = useState(createInitialStaffFormState)
  const { release, confirmDiscard } = useFormPageRefresh({
    values: formState,
    isLoading: isMasterDataLoading,
    reload: reloadRegistration,
    baseline: initialFormState,
    isComplete: submissionStatus === 'success',
  })

  // Cancel asks first once anything has been entered (QA: it used to
  // discard silently).
  const cancelRegistration = () => {
    confirmDiscard(() => {
      release()
      reset()
      navigate('/staff/invitations')
    })
  }

  return (
    <GroupErrorsContext.Provider value={errors}>
      <PageContentLayout
        rootRef={rootRef}
        bodyRef={formRegionRef}
        bodyClassName="scrollbar-thin"
        header={
          <>
            <RegistrationWorkspaceHeader />
            <RegistrationStepper steps={stepLabels} currentStep={currentStep} onStepSelect={goToStep} />
          </>
        }
        // The Review step has its own sticky Back/Submit bar; showing this
        // one too stacked two sticky bars on a phone.
        footer={
          activeStep?.key === 'review_confirm' ? undefined : (
            <div className="sticky bottom-0 -mx-4 flex flex-none flex-wrap items-center justify-between gap-3 border-t border-border bg-surface px-4 pt-4 pb-1 lg:static lg:mx-0 lg:px-0 lg:pb-0">
              <button
                type="button"
                onClick={cancelRegistration}
                title="Cancel this registration"
                className="cursor-pointer rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary transition-colors hover:bg-primary/10"
              >
                Cancel
              </button>
              {!isFormConfigLoading && !formConfigError && activeStep?.key !== 'review_confirm' && (
                <button
                  type="button"
                  onClick={goNext}
                  title="Continue to the next step"
                  className="cursor-pointer rounded-lg bg-primary px-7 py-3 text-body font-semibold text-on-primary transition-colors hover:opacity-90"
                >
                  {nextStepLabel ? `Next: ${nextStepLabel} →` : 'Next →'}
                </button>
              )}
            </div>
          )
        }
      >
        <div className="flex flex-col overflow-x-clip rounded-2xl border border-border bg-surface p-4 md:p-6">
          <div key={currentStep} data-direction={stepDirection} className="step-enter flex flex-col gap-6">
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
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
                errors={errors}
                visitorCategories={visitorCategories}
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
                stickyBarInsetClassName="-mx-4 -mb-4 px-4 md:-mx-6 md:-mb-6 md:px-6"
                formState={formState}
                status={submissionStatus}
                trackingId={trackingId}
                confirmedFullName={confirmedFullName}
                errorMessage={submissionError}
                visitorCategories={visitorCategories}
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
                onGoHome={cancelRegistration}
                homeLabel="Back to Dashboard"
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
        </div>
      </PageContentLayout>
    </GroupErrorsContext.Provider>
  )
}
