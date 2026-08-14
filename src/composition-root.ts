import { ApiClient } from './data/api/api-client'
import type { VisitRequestRepository } from './data/repositories/visit-request-repository'
import type { VisitRequestSummaryRepository } from './data/repositories/visit-request-summary-repository'
import type { VisitTrackingRepository } from './data/repositories/visit-tracking-repository'
import type { VisitorOtpRepository } from './data/repositories/visitor-otp-repository'
import type { StaffAuthRepository } from './data/repositories/staff-auth-repository'
import type { StaffVisitRequestRepository } from './data/repositories/staff-visit-request-repository'
import { SubmitVisitRequestUseCase } from './data/use-cases/submit-visit-request'
import { SubmitStaffVisitRequestUseCase } from './data/use-cases/submit-staff-visit-request'
import { TrackVisitRequestUseCase } from './data/use-cases/track-visit-request'
import { UploadVisitorDocumentUseCase } from './data/use-cases/upload-visitor-document'
import { RequestVisitorOtpUseCase } from './data/use-cases/request-visitor-otp'
import { VerifyVisitorOtpUseCase } from './data/use-cases/verify-visitor-otp'
import { InitiateStaffSsoUseCase } from './data/use-cases/initiate-staff-sso'
import { ListVisitRequestsUseCase } from './data/use-cases/list-visit-requests'
import { GetCurrentStaffUserUseCase } from './data/use-cases/get-current-staff-user'
import { HttpVisitRequestRepository } from './infrastructure/visit-request-repository'
import { HttpVisitRequestSummaryRepository } from './infrastructure/visit-request-summary-repository'
import { HttpVisitTrackingRepository } from './infrastructure/visit-tracking-repository'
import { HttpVisitorOtpRepository } from './infrastructure/visitor-otp-repository'
import { HttpStaffAuthRepository } from './infrastructure/staff-auth-repository'
import { HttpStaffVisitRequestRepository } from './infrastructure/staff-visit-request-repository'

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
  }
}
