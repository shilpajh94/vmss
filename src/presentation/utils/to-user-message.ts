import { ApiError, describeApiField, isFallbackErrorMessage } from '../../data/api/api-error'

// The message a failed save or delete should show (async-ui-states "Server
// Validation and Conflict Messages Reach the User"). A 4xx whose envelope
// names the problem (a duplicate code 409, a 422 on one field) shows that;
// a network failure, a 5xx, a body with no message, or anything that isn't
// an `ApiError` (a Zod parse error is not something to show a user) gets the
// caller's generic `fallback`. A 422 listing field errors leads with the
// first one, which reads better than the envelope's "Invalid request: a.b: …"
// summary.
export function toUserMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError) || error.status >= 500) return fallback
  const [firstField] = Object.entries(error.fieldErrors)
  if (firstField) {
    const [field, message] = firstField
    return field && field !== 'payload' ? `${describeApiField(field)}: ${message}` : message
  }
  const message = error.message.trim()
  return message && !isFallbackErrorMessage(message) ? message : fallback
}

// The API's message for one field, matched on the last segment of the path it
// names (`body.name`, `name`), for a form that shows errors next to fields.
export function apiFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {}
  const fieldErrors: Record<string, string> = {}
  for (const [field, message] of Object.entries(error.fieldErrors)) {
    const key = field.split('.').pop()
    if (key && !(key in fieldErrors)) fieldErrors[key] = message
  }
  return fieldErrors
}
