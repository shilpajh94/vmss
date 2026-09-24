import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { StaffUser } from '../../../domain/entities/staff-user-schema'
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

export function StaffVisitorRegistrationPage() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listBranchesUseCase, listBuildingsUseCase, listVisitorCategoriesUseCase } = useAppDependencies()
  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[] | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[] | undefined>(undefined)
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[] | undefined>(undefined)

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
    reset,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
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
  } = useStaffVisitorRegistrationWizard(branches)

  const stepLabels = isFormConfigLoading ? getSkeletonStepLabels() : activeSteps.map(resolveStepLabel)
  const activeStep = activeSteps[currentStep]
  const nextStepLabel = activeSteps[currentStep + 1] ? resolveStepLabel(activeSteps[currentStep + 1]) : undefined

  const loadCurrentUser = useCallback(async () => {
    try {
      setCurrentUser(await getCurrentStaffUserUseCase.execute())
    } catch {
      // The header simply omits the identity block if this fails; the wizard itself still works.
    }
  }, [getCurrentStaffUserUseCase])

  const loadVisitInfoMasterData = useCallback(async () => {
    try {
      const [branchList, buildingList, categoryList] = await Promise.all([
        listBranchesUseCase.execute(),
        listBuildingsUseCase.execute(),
        listVisitorCategoriesUseCase.execute(),
      ])
      setBranches(branchList)
      setBuildings(buildingList)
      setVisitorCategories(categoryList)
    } catch (error) {
      // Visit Info step falls back to free-text fields if master data can't be loaded.
      console.error('Failed to load visit info master data', error)
    }
  }, [listBranchesUseCase, listBuildingsUseCase, listVisitorCategoriesUseCase])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }
    void loadCurrentUser()
    void loadVisitInfoMasterData()
  }, [navigate, loadCurrentUser, loadVisitInfoMasterData])

  const signOut = () => {
    sessionStorage.removeItem('token')
    navigate('/staff/login')
  }

  const cancelRegistration = () => {
    reset()
    navigate('/staff/dashboard')
  }

  return (
    <>
      <RegistrationWorkspaceHeader currentUser={currentUser} onSignOut={signOut} />

      <RegistrationStepper steps={stepLabels} currentStep={currentStep} onStepSelect={goToStep} />

      <div className="flex flex-1 flex-col gap-6 rounded-2xl border border-border bg-surface p-6">
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
            customFieldValues={formState.customFieldValues}
            onCustomFieldValuesChange={(customFieldValues) => setFormState({ ...formState, customFieldValues })}
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
            visitorCategories={visitorCategories}
            getFilePreviewUrl={getFilePreviewUrl}
            vehicleCustomFields={vehicleInfoCustomFields}
            carriedItemsCustomFields={carriedItemsFields.filter((field) => !field.isSystem)}
            visitorInfoGroups={visitorInfoGroups}
            visitorInfoAllFields={visitorInfoAllFields}
            vehicleInfoGroups={vehicleInfoGroups}
            vehicleInfoAllFields={vehicleInfoAllFields}
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

      <div className="flex items-center justify-between border-t border-border pt-4">
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
            className="cursor-pointer rounded-lg bg-primary px-7 py-3 text-body font-semibold text-white transition-colors hover:opacity-90"
          >
            {nextStepLabel ? `Next: ${nextStepLabel} →` : 'Next →'}
          </button>
        )}
      </div>
    </>
  )
}
