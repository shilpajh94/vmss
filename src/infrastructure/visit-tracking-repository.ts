import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitTrackingRepository } from '../data/repositories/visit-tracking-repository'
import { InvitationTrackResponseSchema, type InvitationTrackOut } from '../domain/entities/invitation-track-out-schema'
import type { TrackingLookupResponse } from '../domain/entities/tracking-lookup-response-schema'

// The statuses the API writes (`InvitationStatus`), each with its label,
// tone and the timeline step it leaves in progress. `submitted` waits on
// approval; `denied` stops there; `archived` is an approved visit that
// never happened.
const STATUSES: Record<string, Pick<TrackingLookupResponse, 'statusLabel' | 'statusTone' | 'timelineStage'>> = {
  submitted: { statusLabel: 'Under Review', statusTone: 'info', timelineStage: 'approved' },
  approved: { statusLabel: 'Approved', statusTone: 'success', timelineStage: 'checked-in' },
  denied: { statusLabel: 'Denied', statusTone: 'danger', timelineStage: 'approved' },
  checked_in: { statusLabel: 'Checked In', statusTone: 'success', timelineStage: 'checked-out' },
  checked_out: { statusLabel: 'Checked Out', statusTone: 'success', timelineStage: 'complete' },
  archived: { statusLabel: 'Expired', statusTone: 'neutral', timelineStage: 'checked-in' },
}

function humanizeStatus(status: string): string {
  return status
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function toTrackingLookupResponse(invitationOut: InvitationTrackOut): TrackingLookupResponse {
  const normalizedStatus = invitationOut.status.toLowerCase()

  return {
    trackingId: invitationOut.trackingId,
    ...(STATUSES[normalizedStatus] ?? {
      statusLabel: humanizeStatus(invitationOut.status),
      statusTone: 'neutral',
      timelineStage: 'unknown',
    }),
    requestedDate: invitationOut.preferredVisitDate ?? invitationOut.submittedAt ?? '—',
    assignedHost: invitationOut.hostNameOrEmail ?? 'Unassigned',
    totalVisitors: 1 + (invitationOut.visitors?.length ?? 0),
    primaryContactFullName: invitationOut.primaryContactFullName,
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
