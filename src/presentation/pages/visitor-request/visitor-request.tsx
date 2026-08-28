import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { PortalFooter } from '../../components/PortalFooter'
import { PortalHeader } from '../../components/PortalHeader'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { Department } from '../../../domain/entities/department-schema'
import type { EmployeeDirectoryEntry } from '../../../domain/entities/employee-directory-schema'
import type { VisitorCategory } from '../../../domain/entities/visitor-category-schema'
import { OtpRequestScreen } from './Components/otp/OtpRequestScreen'
import { OtpScreenLayout } from './Components/otp/OtpScreenLayout'
import { OtpVerifyScreen } from './Components/otp/OtpVerifyScreen'
import { StepSidebar } from './Components/StepSidebar'
import { CarriedItemsStep } from './Components/steps/CarriedItemsStep'
import { ConsentStep } from './Components/steps/ConsentStep'
import { ReviewConfirmStep } from './Components/steps/ReviewConfirmStep'
import { VehicleInfoStep } from './Components/steps/VehicleInfoStep'
import { VisitInfoStep } from './Components/steps/VisitInfoStep'
import { VisitorInfoStep } from './Components/steps/VisitorInfoStep'
import { useVisitorOtp } from './hooks/use-visitor-otp'
import { useVisitorRequestWizard, type VisitorRequestWizardInitialData } from './hooks/use-visitor-request-wizard'

function VisitorRequestWizard({ initial }: { initial?: VisitorRequestWizardInitialData }) {
  const { currentStep, formState, setFormState, errors, goNext, goBack, uploadFile, submissionStatus, trackingId, submissionError, submit } =
    useVisitorRequestWizard(initial)

  const { listVisitorCategoriesUseCase, listEmployeeDirectoryUseCase, listBranchesUseCase, listBuildingsUseCase, listDepartmentsUseCase } =
    useAppDependencies()
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[] | undefined>(undefined)
  const [hostEmployees, setHostEmployees] = useState<EmployeeDirectoryEntry[] | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[] | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[] | undefined>(undefined)
  const [departments, setDepartments] = useState<Department[] | undefined>(undefined)

  const loadVisitorCategories = useCallback(async () => {
    try {
      setVisitorCategories(await listVisitorCategoriesUseCase.execute())
    } catch {
      // Falls back to no options; the field stays empty if this fails.
    }
  }, [listVisitorCategoriesUseCase])

  // Each call is caught independently — a Promise.all would let one rejection
  // block every field's data.
  const loadVisitInfoMasterData = useCallback(() => {
    listEmployeeDirectoryUseCase
      .execute()
      .then(setHostEmployees)
      .catch(() => {
        // Falls back to a free-text Host Name or Email field.
      })
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
    listDepartmentsUseCase
      .execute()
      .then(setDepartments)
      .catch(() => {
        // Falls back to a free-text Department to Visit field.
      })
  }, [listEmployeeDirectoryUseCase, listBranchesUseCase, listBuildingsUseCase, listDepartmentsUseCase])

  useEffect(() => {
    void loadVisitorCategories()
    loadVisitInfoMasterData()
  }, [loadVisitorCategories, loadVisitInfoMasterData])

  return (
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
            visitorCategories={visitorCategories}
          />
        )}
        {currentStep === 1 && (
          <VisitInfoStep
            value={formState.visitInfo}
            onChange={(visitInfo) => setFormState({ ...formState, visitInfo })}
            errors={errors}
            hostEmployees={hostEmployees}
            branches={branches}
            buildings={buildings}
            departments={departments}
          />
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
