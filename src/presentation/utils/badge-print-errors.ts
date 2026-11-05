import { ApiError } from '../../data/api/api-error'

export const BADGE_FLOW_UNAVAILABLE = 'unavailable'

// 404 on any /checkin route means the feature is off (server flag or tenant
// toggle) - except the backend's own "Visit not found", which only means that
// one row is stale (shown as a normal error, the list is refreshed).
export function isFeatureOff(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && !/visit not found/i.test(error.message)
}

const PREREQUISITE_COPY: ReadonlyArray<readonly [code: string, copy: string]> = [
  ['visit_not_approved', 'This visit is not approved yet, so a badge cannot be printed.'],
  ['photo_missing', "A photo has not been captured for this visitor yet."],
  ['id_not_verified', 'ID verification is currently required before printing. Turn off "Require ID verification before printing badge" in Organisation Configs to verify at check-in instead.'],
]

// Print/reprint 409s name what is missing in the message; anything else is the
// "badge already active" / "reprint before first print" case, or an unknown 409.
export function describePrintError(error: unknown, mode: 'print' | 'reprint'): string {
  if (!(error instanceof ApiError)) return 'Something went wrong. Please try again.'
  if (error.status === 409) {
    const known = PREREQUISITE_COPY.find(([code]) => error.message.includes(code))
    if (known) return known[1]
    const lower = error.message.toLowerCase()
    if (mode === 'print' && lower.includes('active')) return 'A badge is already active for this visit. Use Reprint to replace it.'
    if (mode === 'reprint' && (lower.includes('first') || lower.includes('no badge') || lower.includes('not printed')))
      return 'No badge has been printed for this visit yet. Use Print badge first.'
    return error.message
  }
  return error.message || 'Something went wrong. Please try again.'
}

// Check-in 409 when the tenant enforces ID verification at check-in instead of
// at print time ("ID not verified; verify ID before check-in ...").
export function isIdNotVerifiedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && /id not verified/i.test(error.message)
}
