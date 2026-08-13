import type { TrackingLookupResponse } from '../../domain/entities/tracking-lookup-response-schema'

export interface VisitTrackingRepository {
  lookup(trackingId: string): Promise<TrackingLookupResponse>
}
