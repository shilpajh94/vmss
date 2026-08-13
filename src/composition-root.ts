import { ApiClient } from './data/api/api-client'
import type { VisitRequestRepository } from './data/repositories/visit-request-repository'
import type { VisitTrackingRepository } from './data/repositories/visit-tracking-repository'
import { SubmitVisitRequestUseCase } from './data/use-cases/submit-visit-request'
import { TrackVisitRequestUseCase } from './data/use-cases/track-visit-request'
import { UploadVisitorDocumentUseCase } from './data/use-cases/upload-visitor-document'
import { HttpVisitRequestRepository } from './infrastructure/visit-request-repository'
import { HttpVisitTrackingRepository } from './infrastructure/visit-tracking-repository'

export interface AppDependencies {
  apiClient: ApiClient
  submitVisitRequestUseCase: SubmitVisitRequestUseCase
  uploadVisitorDocumentUseCase: UploadVisitorDocumentUseCase
  trackVisitRequestUseCase: TrackVisitRequestUseCase
}

export function createApp(): AppDependencies {
  let apiClient: ApiClient | undefined
  let visitRequestRepository: VisitRequestRepository | undefined
  let visitTrackingRepository: VisitTrackingRepository | undefined
  let submitVisitRequestUseCase: SubmitVisitRequestUseCase | undefined
  let uploadVisitorDocumentUseCase: UploadVisitorDocumentUseCase | undefined
  let trackVisitRequestUseCase: TrackVisitRequestUseCase | undefined

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
  }
}
