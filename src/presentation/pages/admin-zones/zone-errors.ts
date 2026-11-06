import { ApiError } from '../../../data/api/api-error'
import { toUserMessage } from '../../utils/to-user-message'

export const DEFAULT_ZONE_CONFLICT_MESSAGE = 'Choose another default zone first.'

/** A 409 on a zone write means the zone is the branch default and cannot be deleted or deactivated. */
export function zoneWriteMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.status === 409 ? DEFAULT_ZONE_CONFLICT_MESSAGE : toUserMessage(error, fallback)
}
