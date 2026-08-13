import type { VisitTrackingRepository } from '../repositories/visit-tracking-repository'
import type { TrackingLookupResponse } from '../../domain/entities/tracking-lookup-response-schema'

export class TrackVisitRequestUseCase {
  private readonly visitTrackingRepository: VisitTrackingRepository

  constructor(visitTrackingRepository: VisitTrackingRepository) {
    this.visitTrackingRepository = visitTrackingRepository
  }

  async execute(trackingId: string): Promise<TrackingLookupResponse> {
    return this.visitTrackingRepository.lookup(trackingId)
  }
}
