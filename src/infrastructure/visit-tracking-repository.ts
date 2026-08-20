import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitTrackingRepository } from '../data/repositories/visit-tracking-repository'
import { InvitationTrackResponseSchema, type InvitationTrackOut } from '../domain/entities/invitation-track-out-schema'
import type { TrackingLookupResponse } from '../domain/entities/tracking-lookup-response-schema'

const STATUS_LABELS: Record<string, string> = {
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
  visit_day: 'Visit Day',
  checked_in: 'Checked In',
  completed: 'Completed',
  cancelled: 'Cancelled',
  expired: 'Expired',
}

const STATUS_TONE: Record<string, TrackingLookupResponse['statusTone']> = {
  submitted: 'info',
  under_review: 'warning',
  approved: 'success',
  rejected: 'danger',
  visit_day: 'success',
  checked_in: 'success',
  completed: 'success',
  cancelled: 'danger',
  expired: 'danger',
}

const STATUS_TIMELINE_STAGE: Record<string, TrackingLookupResponse['timelineStage']> = {
  submitted: 'submitted',
  under_review: 'under-review',
  approved: 'approved',
  visit_day: 'visit-day',
  checked_in: 'visit-day',
  completed: 'visit-day',
  rejected: 'submitted',
  cancelled: 'submitted',
  expired: 'submitted',
}

function humanizeStatus(status: string): string {
  return status
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function toTrackingLookupResponse(invitationOut: InvitationTrackOut): TrackingLookupResponse {
  const normalizedStatus = invitationOut.status.toLowerCase()

  return {
    trackingId: invitationOut.trackingId,
    statusLabel: STATUS_LABELS[normalizedStatus] ?? humanizeStatus(invitationOut.status),
    statusTone: STATUS_TONE[normalizedStatus] ?? 'info',
    requestedDate: invitationOut.preferredVisitDate ?? invitationOut.submittedAt ?? '—',
    assignedHost: invitationOut.hostNameOrEmail ?? 'Unassigned',
    totalVisitors: invitationOut.visitors && invitationOut.visitors.length > 0 ? invitationOut.visitors.length : 1,
    timelineStage: STATUS_TIMELINE_STAGE[normalizedStatus] ?? 'submitted',
  }
}

export class HttpVisitTrackingRepository implements VisitTrackingRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async lookup(trackingId: string): Promise<TrackingLookupResponse> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.TRACK_VISIT_REQUEST,
      queryParams: { trackingId },
      parserSchema: InvitationTrackResponseSchema,
    })

    return toTrackingLookupResponse(response.data)
  }
}
