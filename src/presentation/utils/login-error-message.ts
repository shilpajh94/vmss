import { ApiError } from '../../data/api/api-error'

// A failed sign-in is not always bad credentials: the per-IP limiter (429)
// and an unreachable or failing server need their own copy, or the user
// keeps retyping a correct password.
export function loginErrorMessage(error: unknown, credentialsMessage: string): string {
  if (error instanceof ApiError && error.status === 429) {
    return 'Too many sign-in attempts. Please wait a minute and try again.'
  }
  if ((error instanceof ApiError && error.status >= 500) || error instanceof TypeError) {
    return "Can't reach the server. Check your connection and try again."
  }
  return credentialsMessage
}
