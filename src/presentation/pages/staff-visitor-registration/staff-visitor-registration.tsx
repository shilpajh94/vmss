import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { DashboardSidebar } from '../../components/DashboardSidebar'
import { useAppDependencies } from '../../context/app-dependencies-context'
import type { Branch } from '../../../domain/entities/branch-schema'
import type { Building } from '../../../domain/entities/building-schema'
import type { Department } from '../../../domain/entities/department-schema'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import type { StaffUser } from '../../../domain/entities/staff-user-schema'
import type { VisitorCategory } from '../../../domain/entities/visitor-category-schema'
import { CarriedItemsStep } from '../visitor-request/Components/steps/CarriedItemsStep'
import { ConsentStep } from '../visitor-request/Components/steps/ConsentStep'
import { ReviewConfirmStep } from '../visitor-request/Components/steps/ReviewConfirmStep'
import { VehicleInfoStep } from '../visitor-request/Components/steps/VehicleInfoStep'
import { VisitInfoStep } from '../visitor-request/Components/steps/VisitInfoStep'
import { RegistrationStepper } from './Components/RegistrationStepper'
import { RegistrationWorkspaceHeader } from './Components/RegistrationWorkspaceHeader'
import { VisitorInfoStep } from './Components/VisitorInfoStep'
import { useStaffVisitorRegistrationWizard } from './hooks/use-staff-visitor-registration-wizard'
import { STAFF_WIZARD_STEPS } from './types'

export function StaffVisitorRegistrationPage() {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listHostEmployeesUseCase,
    listBranchesUseCase,
    listBuildingsUseCase,
    listDepartmentsUseCase,
    listVisitorCategoriesUseCase,
  } = useAppDependencies()
  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[] | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[] | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[] | undefined>(undefined)
  const [departments, setDepartments] = useState<Department[] | undefined>(undefined)
  const [visitorCategories, setVisitorCategories] = useState<VisitorCategory[] | undefined>(undefined)

  const {
    currentStep,
    formState,
    setFormState,
    errors,
    goNext,
    goBack,
    uploadFile,
    submissionStatus,
    trackingId,
    submissionError,
    submit,
    reset,
  } = useStaffVisitorRegistrationWizard(branches)

  const loadCurrentUser = useCallback(async () => {
    try {
      setCurrentUser(await getCurrentStaffUserUseCase.execute())
    } catch {
      // The header simply omits the identity block if this fails; the wizard itself still works.
    }
  }, [getCurrentStaffUserUseCase])

  const loadVisitInfoMasterData = useCallback(async () => {
    try {
      const [employees, branchList, buildingList, departmentList, categoryList] = await Promise.all([
        listHostEmployeesUseCase.execute(),
        listBranchesUseCase.execute(),
        listBuildingsUseCase.execute(),
        listDepartmentsUseCase.execute(),
        listVisitorCategoriesUseCase.execute(),
      ])
      setHostEmployees(employees)
      setBranches(branchList)
      setBuildings(buildingList)
      setDepartments(departmentList)
      setVisitorCategories(categoryList)
    } catch {
      // Visit Info step falls back to free-text fields if master data can't be loaded.
    }
  }, [listHostEmployeesUseCase, listBranchesUseCase, listBuildingsUseCase, listDepartmentsUseCase, listVisitorCategoriesUseCase])

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
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <DashboardSidebar activeItem="my-actions" />

      <main className="flex flex-1 flex-col">
        <RegistrationWorkspaceHeader currentUser={currentUser} onSignOut={signOut} />

        <div className="flex flex-1 flex-col gap-6 px-10 py-8">
          <RegistrationStepper steps={STAFF_WIZARD_STEPS} currentStep={currentStep} />

          <div className="flex flex-1 flex-col gap-6 rounded-2xl border border-border bg-surface p-6">
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
          </div>

          <div className="flex items-center justify-between border-t border-border pt-4">
            <button
              type="button"
              onClick={cancelRegistration}
              className="rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary"
            >
              Cancel
            </button>
            {currentStep < 5 && (
              <button type="button" onClick={goNext} className="rounded-lg bg-primary px-7 py-3 text-body font-semibold text-white">
                Next: {STAFF_WIZARD_STEPS[currentStep + 1]} →
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
