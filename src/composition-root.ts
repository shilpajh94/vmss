import { ApiClient } from './data/api/api-client'
import type { VisitRequestRepository } from './data/repositories/visit-request-repository'
import type { VisitRequestSummaryRepository } from './data/repositories/visit-request-summary-repository'
import type { VisitTrackingRepository } from './data/repositories/visit-tracking-repository'
import type { VisitorOtpRepository } from './data/repositories/visitor-otp-repository'
import type { StaffAuthRepository } from './data/repositories/staff-auth-repository'
import type { StaffVisitRequestRepository } from './data/repositories/staff-visit-request-repository'
import type { AuditTrailRepository } from './data/repositories/audit-trail-repository'
import type { OrganisationConfigRepository } from './data/repositories/organisation-config-repository'
import type { BranchRepository } from './data/repositories/branch-repository'
import type { DepartmentRepository } from './data/repositories/department-repository'
import type { BuildingRepository } from './data/repositories/building-repository'
import { SubmitVisitRequestUseCase } from './data/use-cases/submit-visit-request'
import { SubmitStaffVisitRequestUseCase } from './data/use-cases/submit-staff-visit-request'
import { GetAuditTrailUseCase } from './data/use-cases/get-audit-trail'
import { TrackVisitRequestUseCase } from './data/use-cases/track-visit-request'
import { UploadVisitorDocumentUseCase } from './data/use-cases/upload-visitor-document'
import { RequestVisitorOtpUseCase } from './data/use-cases/request-visitor-otp'
import { VerifyVisitorOtpUseCase } from './data/use-cases/verify-visitor-otp'
import { InitiateStaffSsoUseCase } from './data/use-cases/initiate-staff-sso'
import { ListVisitRequestsUseCase } from './data/use-cases/list-visit-requests'
import { GetCurrentStaffUserUseCase } from './data/use-cases/get-current-staff-user'
import { GetOrganisationConfigUseCase } from './data/use-cases/get-organisation-config'
import { UpdateOrganisationConfigUseCase } from './data/use-cases/update-organisation-config'
import { UploadOrganisationLogoUseCase } from './data/use-cases/upload-organisation-logo'
import { ListBranchesUseCase } from './data/use-cases/list-branches'
import { CreateBranchUseCase } from './data/use-cases/create-branch'
import { UpdateBranchUseCase } from './data/use-cases/update-branch'
import { DeleteBranchUseCase } from './data/use-cases/delete-branch'
import { ListDepartmentsUseCase } from './data/use-cases/list-departments'
import { CreateDepartmentUseCase } from './data/use-cases/create-department'
import { UpdateDepartmentUseCase } from './data/use-cases/update-department'
import { DeleteDepartmentUseCase } from './data/use-cases/delete-department'
import { ListBuildingsUseCase } from './data/use-cases/list-buildings'
import { CreateBuildingUseCase } from './data/use-cases/create-building'
import { UpdateBuildingUseCase } from './data/use-cases/update-building'
import { DeleteBuildingUseCase } from './data/use-cases/delete-building'
import { HttpVisitRequestRepository } from './infrastructure/visit-request-repository'
import { HttpVisitRequestSummaryRepository } from './infrastructure/visit-request-summary-repository'
import { HttpVisitTrackingRepository } from './infrastructure/visit-tracking-repository'
import { HttpVisitorOtpRepository } from './infrastructure/visitor-otp-repository'
import { HttpStaffAuthRepository } from './infrastructure/staff-auth-repository'
import { HttpStaffVisitRequestRepository } from './infrastructure/staff-visit-request-repository'
import { HttpAuditTrailRepository } from './infrastructure/audit-trail-repository'
import { HttpOrganisationConfigRepository } from './infrastructure/organisation-config-repository'
import { HttpBranchRepository } from './infrastructure/branch-repository'
import { HttpDepartmentRepository } from './infrastructure/department-repository'
import { HttpBuildingRepository } from './infrastructure/building-repository'

export interface AppDependencies {
  apiClient: ApiClient
  submitVisitRequestUseCase: SubmitVisitRequestUseCase
  uploadVisitorDocumentUseCase: UploadVisitorDocumentUseCase
  trackVisitRequestUseCase: TrackVisitRequestUseCase
  requestVisitorOtpUseCase: RequestVisitorOtpUseCase
  verifyVisitorOtpUseCase: VerifyVisitorOtpUseCase
  initiateStaffSsoUseCase: InitiateStaffSsoUseCase
  listVisitRequestsUseCase: ListVisitRequestsUseCase
  getCurrentStaffUserUseCase: GetCurrentStaffUserUseCase
  submitStaffVisitRequestUseCase: SubmitStaffVisitRequestUseCase
  getAuditTrailUseCase: GetAuditTrailUseCase
  getOrganisationConfigUseCase: GetOrganisationConfigUseCase
  updateOrganisationConfigUseCase: UpdateOrganisationConfigUseCase
  uploadOrganisationLogoUseCase: UploadOrganisationLogoUseCase
  listBranchesUseCase: ListBranchesUseCase
  createBranchUseCase: CreateBranchUseCase
  updateBranchUseCase: UpdateBranchUseCase
  deleteBranchUseCase: DeleteBranchUseCase
  listDepartmentsUseCase: ListDepartmentsUseCase
  createDepartmentUseCase: CreateDepartmentUseCase
  updateDepartmentUseCase: UpdateDepartmentUseCase
  deleteDepartmentUseCase: DeleteDepartmentUseCase
  listBuildingsUseCase: ListBuildingsUseCase
  createBuildingUseCase: CreateBuildingUseCase
  updateBuildingUseCase: UpdateBuildingUseCase
  deleteBuildingUseCase: DeleteBuildingUseCase
}

export function createApp(): AppDependencies {
  let apiClient: ApiClient | undefined
  let visitRequestRepository: VisitRequestRepository | undefined
  let visitRequestSummaryRepository: VisitRequestSummaryRepository | undefined
  let visitTrackingRepository: VisitTrackingRepository | undefined
  let visitorOtpRepository: VisitorOtpRepository | undefined
  let staffAuthRepository: StaffAuthRepository | undefined
  let submitVisitRequestUseCase: SubmitVisitRequestUseCase | undefined
  let uploadVisitorDocumentUseCase: UploadVisitorDocumentUseCase | undefined
  let trackVisitRequestUseCase: TrackVisitRequestUseCase | undefined
  let requestVisitorOtpUseCase: RequestVisitorOtpUseCase | undefined
  let verifyVisitorOtpUseCase: VerifyVisitorOtpUseCase | undefined
  let initiateStaffSsoUseCase: InitiateStaffSsoUseCase | undefined
  let listVisitRequestsUseCase: ListVisitRequestsUseCase | undefined
  let getCurrentStaffUserUseCase: GetCurrentStaffUserUseCase | undefined
  let staffVisitRequestRepository: StaffVisitRequestRepository | undefined
  let submitStaffVisitRequestUseCase: SubmitStaffVisitRequestUseCase | undefined
  let auditTrailRepository: AuditTrailRepository | undefined
  let getAuditTrailUseCase: GetAuditTrailUseCase | undefined
  let organisationConfigRepository: OrganisationConfigRepository | undefined
  let getOrganisationConfigUseCase: GetOrganisationConfigUseCase | undefined
  let updateOrganisationConfigUseCase: UpdateOrganisationConfigUseCase | undefined
  let uploadOrganisationLogoUseCase: UploadOrganisationLogoUseCase | undefined
  let branchRepository: BranchRepository | undefined
  let listBranchesUseCase: ListBranchesUseCase | undefined
  let createBranchUseCase: CreateBranchUseCase | undefined
  let updateBranchUseCase: UpdateBranchUseCase | undefined
  let deleteBranchUseCase: DeleteBranchUseCase | undefined
  let departmentRepository: DepartmentRepository | undefined
  let listDepartmentsUseCase: ListDepartmentsUseCase | undefined
  let createDepartmentUseCase: CreateDepartmentUseCase | undefined
  let updateDepartmentUseCase: UpdateDepartmentUseCase | undefined
  let deleteDepartmentUseCase: DeleteDepartmentUseCase | undefined
  let buildingRepository: BuildingRepository | undefined
  let listBuildingsUseCase: ListBuildingsUseCase | undefined
  let createBuildingUseCase: CreateBuildingUseCase | undefined
  let updateBuildingUseCase: UpdateBuildingUseCase | undefined
  let deleteBuildingUseCase: DeleteBuildingUseCase | undefined

  const resolveApiClient = (): ApiClient => {
    apiClient ??= new ApiClient(import.meta.env.VITE_API_BASE_URL)
    return apiClient
  }

  const resolveVisitRequestRepository = (): VisitRequestRepository => {
    visitRequestRepository ??= new HttpVisitRequestRepository(resolveApiClient())
    return visitRequestRepository
  }

  const resolveVisitTrackingRepository = (): VisitTrackingRepository => {
    visitTrackingRepository ??= new HttpVisitTrackingRepository(resolveApiClient())
    return visitTrackingRepository
  }

  const resolveSubmitVisitRequestUseCase = (): SubmitVisitRequestUseCase => {
    submitVisitRequestUseCase ??= new SubmitVisitRequestUseCase(resolveVisitRequestRepository())
    return submitVisitRequestUseCase
  }

  const resolveUploadVisitorDocumentUseCase = (): UploadVisitorDocumentUseCase => {
    uploadVisitorDocumentUseCase ??= new UploadVisitorDocumentUseCase(resolveVisitRequestRepository())
    return uploadVisitorDocumentUseCase
  }

  const resolveTrackVisitRequestUseCase = (): TrackVisitRequestUseCase => {
    trackVisitRequestUseCase ??= new TrackVisitRequestUseCase(resolveVisitTrackingRepository())
    return trackVisitRequestUseCase
  }

  const resolveVisitorOtpRepository = (): VisitorOtpRepository => {
    visitorOtpRepository ??= new HttpVisitorOtpRepository(resolveApiClient())
    return visitorOtpRepository
  }

  const resolveRequestVisitorOtpUseCase = (): RequestVisitorOtpUseCase => {
    requestVisitorOtpUseCase ??= new RequestVisitorOtpUseCase(resolveVisitorOtpRepository())
    return requestVisitorOtpUseCase
  }

  const resolveVerifyVisitorOtpUseCase = (): VerifyVisitorOtpUseCase => {
    verifyVisitorOtpUseCase ??= new VerifyVisitorOtpUseCase(resolveVisitorOtpRepository())
    return verifyVisitorOtpUseCase
  }

  const resolveStaffAuthRepository = (): StaffAuthRepository => {
    staffAuthRepository ??= new HttpStaffAuthRepository(resolveApiClient())
    return staffAuthRepository
  }

  const resolveInitiateStaffSsoUseCase = (): InitiateStaffSsoUseCase => {
    initiateStaffSsoUseCase ??= new InitiateStaffSsoUseCase(resolveStaffAuthRepository())
    return initiateStaffSsoUseCase
  }

  const resolveVisitRequestSummaryRepository = (): VisitRequestSummaryRepository => {
    visitRequestSummaryRepository ??= new HttpVisitRequestSummaryRepository(resolveApiClient())
    return visitRequestSummaryRepository
  }

  const resolveListVisitRequestsUseCase = (): ListVisitRequestsUseCase => {
    listVisitRequestsUseCase ??= new ListVisitRequestsUseCase(resolveVisitRequestSummaryRepository())
    return listVisitRequestsUseCase
  }

  const resolveGetCurrentStaffUserUseCase = (): GetCurrentStaffUserUseCase => {
    getCurrentStaffUserUseCase ??= new GetCurrentStaffUserUseCase(resolveStaffAuthRepository())
    return getCurrentStaffUserUseCase
  }

  const resolveStaffVisitRequestRepository = (): StaffVisitRequestRepository => {
    staffVisitRequestRepository ??= new HttpStaffVisitRequestRepository(resolveApiClient())
    return staffVisitRequestRepository
  }

  const resolveSubmitStaffVisitRequestUseCase = (): SubmitStaffVisitRequestUseCase => {
    submitStaffVisitRequestUseCase ??= new SubmitStaffVisitRequestUseCase(resolveStaffVisitRequestRepository())
    return submitStaffVisitRequestUseCase
  }

  const resolveAuditTrailRepository = (): AuditTrailRepository => {
    auditTrailRepository ??= new HttpAuditTrailRepository(resolveApiClient())
    return auditTrailRepository
  }

  const resolveGetAuditTrailUseCase = (): GetAuditTrailUseCase => {
    getAuditTrailUseCase ??= new GetAuditTrailUseCase(resolveAuditTrailRepository())
    return getAuditTrailUseCase
  }

  const resolveOrganisationConfigRepository = (): OrganisationConfigRepository => {
    organisationConfigRepository ??= new HttpOrganisationConfigRepository(resolveApiClient())
    return organisationConfigRepository
  }

  const resolveGetOrganisationConfigUseCase = (): GetOrganisationConfigUseCase => {
    getOrganisationConfigUseCase ??= new GetOrganisationConfigUseCase(resolveOrganisationConfigRepository())
    return getOrganisationConfigUseCase
  }

  const resolveUpdateOrganisationConfigUseCase = (): UpdateOrganisationConfigUseCase => {
    updateOrganisationConfigUseCase ??= new UpdateOrganisationConfigUseCase(resolveOrganisationConfigRepository())
    return updateOrganisationConfigUseCase
  }

  const resolveUploadOrganisationLogoUseCase = (): UploadOrganisationLogoUseCase => {
    uploadOrganisationLogoUseCase ??= new UploadOrganisationLogoUseCase(resolveOrganisationConfigRepository())
    return uploadOrganisationLogoUseCase
  }

  const resolveBranchRepository = (): BranchRepository => {
    branchRepository ??= new HttpBranchRepository(resolveApiClient())
    return branchRepository
  }

  const resolveListBranchesUseCase = (): ListBranchesUseCase => {
    listBranchesUseCase ??= new ListBranchesUseCase(resolveBranchRepository())
    return listBranchesUseCase
  }

  const resolveCreateBranchUseCase = (): CreateBranchUseCase => {
    createBranchUseCase ??= new CreateBranchUseCase(resolveBranchRepository())
    return createBranchUseCase
  }

  const resolveUpdateBranchUseCase = (): UpdateBranchUseCase => {
    updateBranchUseCase ??= new UpdateBranchUseCase(resolveBranchRepository())
    return updateBranchUseCase
  }

  const resolveDeleteBranchUseCase = (): DeleteBranchUseCase => {
    deleteBranchUseCase ??= new DeleteBranchUseCase(resolveBranchRepository())
    return deleteBranchUseCase
  }

  const resolveDepartmentRepository = (): DepartmentRepository => {
    departmentRepository ??= new HttpDepartmentRepository(resolveApiClient())
    return departmentRepository
  }

  const resolveListDepartmentsUseCase = (): ListDepartmentsUseCase => {
    listDepartmentsUseCase ??= new ListDepartmentsUseCase(resolveDepartmentRepository())
    return listDepartmentsUseCase
  }

  const resolveCreateDepartmentUseCase = (): CreateDepartmentUseCase => {
    createDepartmentUseCase ??= new CreateDepartmentUseCase(resolveDepartmentRepository())
    return createDepartmentUseCase
  }

  const resolveUpdateDepartmentUseCase = (): UpdateDepartmentUseCase => {
    updateDepartmentUseCase ??= new UpdateDepartmentUseCase(resolveDepartmentRepository())
    return updateDepartmentUseCase
  }

  const resolveDeleteDepartmentUseCase = (): DeleteDepartmentUseCase => {
    deleteDepartmentUseCase ??= new DeleteDepartmentUseCase(resolveDepartmentRepository())
    return deleteDepartmentUseCase
  }

  const resolveBuildingRepository = (): BuildingRepository => {
    buildingRepository ??= new HttpBuildingRepository(resolveApiClient())
    return buildingRepository
  }

  const resolveListBuildingsUseCase = (): ListBuildingsUseCase => {
    listBuildingsUseCase ??= new ListBuildingsUseCase(resolveBuildingRepository())
    return listBuildingsUseCase
  }

  const resolveCreateBuildingUseCase = (): CreateBuildingUseCase => {
    createBuildingUseCase ??= new CreateBuildingUseCase(resolveBuildingRepository())
    return createBuildingUseCase
  }

  const resolveUpdateBuildingUseCase = (): UpdateBuildingUseCase => {
    updateBuildingUseCase ??= new UpdateBuildingUseCase(resolveBuildingRepository())
    return updateBuildingUseCase
  }

  const resolveDeleteBuildingUseCase = (): DeleteBuildingUseCase => {
    deleteBuildingUseCase ??= new DeleteBuildingUseCase(resolveBuildingRepository())
    return deleteBuildingUseCase
  }

  return {
    get apiClient() {
      return resolveApiClient()
    },
    get submitVisitRequestUseCase() {
      return resolveSubmitVisitRequestUseCase()
    },
    get uploadVisitorDocumentUseCase() {
      return resolveUploadVisitorDocumentUseCase()
    },
    get trackVisitRequestUseCase() {
      return resolveTrackVisitRequestUseCase()
    },
    get requestVisitorOtpUseCase() {
      return resolveRequestVisitorOtpUseCase()
    },
    get verifyVisitorOtpUseCase() {
      return resolveVerifyVisitorOtpUseCase()
    },
    get initiateStaffSsoUseCase() {
      return resolveInitiateStaffSsoUseCase()
    },
    get listVisitRequestsUseCase() {
      return resolveListVisitRequestsUseCase()
    },
    get getCurrentStaffUserUseCase() {
      return resolveGetCurrentStaffUserUseCase()
    },
    get submitStaffVisitRequestUseCase() {
      return resolveSubmitStaffVisitRequestUseCase()
    },
    get getAuditTrailUseCase() {
      return resolveGetAuditTrailUseCase()
    },
    get getOrganisationConfigUseCase() {
      return resolveGetOrganisationConfigUseCase()
    },
    get updateOrganisationConfigUseCase() {
      return resolveUpdateOrganisationConfigUseCase()
    },
    get uploadOrganisationLogoUseCase() {
      return resolveUploadOrganisationLogoUseCase()
    },
    get listBranchesUseCase() {
      return resolveListBranchesUseCase()
    },
    get createBranchUseCase() {
      return resolveCreateBranchUseCase()
    },
    get updateBranchUseCase() {
      return resolveUpdateBranchUseCase()
    },
    get deleteBranchUseCase() {
      return resolveDeleteBranchUseCase()
    },
    get listDepartmentsUseCase() {
      return resolveListDepartmentsUseCase()
    },
    get createDepartmentUseCase() {
      return resolveCreateDepartmentUseCase()
    },
    get updateDepartmentUseCase() {
      return resolveUpdateDepartmentUseCase()
    },
    get deleteDepartmentUseCase() {
      return resolveDeleteDepartmentUseCase()
    },
    get listBuildingsUseCase() {
      return resolveListBuildingsUseCase()
    },
    get createBuildingUseCase() {
      return resolveCreateBuildingUseCase()
    },
    get updateBuildingUseCase() {
      return resolveUpdateBuildingUseCase()
    },
    get deleteBuildingUseCase() {
      return resolveDeleteBuildingUseCase()
    },
  }
}
