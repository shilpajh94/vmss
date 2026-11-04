import { ApiError } from '../../data/api/api-error'

// `disabled`: the backend's zone access feature is off (404 on `GET /zones`).
// `unknown`: not probed yet, or the probe failed for another reason (403 is a
// missing permission, not "feature off", so it must not claim `disabled`).
export type ZoneFeatureStatus = 'unknown' | 'enabled' | 'disabled'

export function zoneFeatureStatusForError(error: unknown): ZoneFeatureStatus {
  return error instanceof ApiError && error.status === 404 ? 'disabled' : 'unknown'
}
