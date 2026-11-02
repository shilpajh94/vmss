// Turns backend validation errors into copy an end user can act on.
//
// This backend puts the raw `str(pydantic.ValidationError)` dump into an error
// body's `message` field instead of the standard FastAPI `{"detail": [...]}`
// shape, e.g.:
//   "1 validation error for InvitationCreate\nvisitors.3.email\n  value is not
//   a valid email address: An email address must have an @-sign.
//   [type=value_error, input_value='dw', input_type=str]"
// `extractErrorMessage` strips that noise down to "Visitor #4 Email: value is
// not a valid email address...". The standard `{"detail": [{loc, msg}]}` shape
// is also handled directly, in case a future endpoint uses it.

// The field-path line is absent for model-level (`@model_validator`) errors, so it's optional here.
const PYDANTIC_ISSUE_PATTERN = /^(?:([\w.]+)\n)?\s*(.+?)\s*\[type=[^\]]*\]\s*$/gm

// Known backend messages rewritten in plain, actionable language for end users.
const KNOWN_MESSAGES: Record<string, string> = {
  'A group registration must list at least one visitor':
    'Please add at least one visitor to the group before submitting.',
}

// Pydantic wraps custom validator errors as "Value error, <message>"; strip that prefix
// and swap in friendlier copy for messages we recognize.
function cleanMessage(msg: string): string {
  const stripped = msg.replace(/^Value error,\s*/, '').trim()
  return KNOWN_MESSAGES[stripped] ?? stripped
}

function toTitleCase(value: string): string {
  const words = value.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/_/g, ' ')
  return words.replace(/\b\w/g, (char) => char.toUpperCase())
}

// "visitors.3.email" -> "Visitor #4 Email"; "primaryContact.email" -> "Primary Contact Email".
function describeFieldPath(loc: string): string {
  const segments = loc.split('.').filter((segment) => segment !== 'body')
  const labeled: string[] = []
  for (const segment of segments) {
    if (/^\d+$/.test(segment)) {
      const prev = labeled.pop()
      labeled.push(prev ? `${prev.replace(/s$/, '')} #${Number(segment) + 1}` : `Item #${Number(segment) + 1}`)
      continue
    }
    labeled.push(toTitleCase(segment))
  }
  return labeled.join(' ')
}

function humanizePydanticDump(raw: string): string {
  const issues: string[] = []
  let match: RegExpExecArray | null
  PYDANTIC_ISSUE_PATTERN.lastIndex = 0
  while ((match = PYDANTIC_ISSUE_PATTERN.exec(raw)) !== null) {
    const loc = match[1]
    const msg = cleanMessage(match[2].trim())
    issues.push(loc ? `${describeFieldPath(loc)}: ${msg}` : msg)
  }
  return issues.length > 0 ? issues.join(' ') : raw
}

interface FastApiIssue {
  loc?: unknown
  msg?: unknown
}

function humanizeDetailArray(detail: unknown[]): string | undefined {
  const issues = detail
    .filter((item): item is FastApiIssue => typeof item === 'object' && item !== null)
    .map((item) => {
      const msg = typeof item.msg === 'string' ? cleanMessage(item.msg) : undefined
      if (!msg) return undefined
      const loc = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : undefined
      return loc ? `${describeFieldPath(loc)}: ${msg}` : msg
    })
    .filter((issue): issue is string => Boolean(issue))
  return issues.length > 0 ? issues.join(' ') : undefined
}

// Lets callers branch on the HTTP status (e.g. 401 vs 429 vs 404) without
// losing the humanized message above — extends `Error` so every existing
// `err instanceof Error ? err.message : ...` call site keeps working.
//
// `fieldErrors` carries the envelope's per-field problems (`errors: [{field,
// message}]`), keyed by the field path the API names, in the order it listed
// them, so a form can show each next to its control.
export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Readonly<Record<string, string>>

  constructor(message: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

// The message `extractErrorMessage` falls back to when a body carries none.
export function isFallbackErrorMessage(message: string): boolean {
  return /^Request failed with status \d+$/.test(message)
}

// "visitors.0.email" -> "Visitor #1 Email", for showing a field error on its own.
export function describeApiField(field: string): string {
  return describeFieldPath(field)
}

interface EnvelopeFieldError {
  field?: unknown
  message?: unknown
}

export function extractFieldErrors(body: unknown): Record<string, string> {
  if (!body || typeof body !== 'object' || !('errors' in body)) return {}
  const errors = (body as { errors: unknown }).errors
  if (!Array.isArray(errors)) return {}
  const fieldErrors: Record<string, string> = {}
  for (const item of errors as EnvelopeFieldError[]) {
    if (!item || typeof item.field !== 'string' || typeof item.message !== 'string') continue
    if (!(item.field in fieldErrors)) fieldErrors[item.field] = cleanMessage(item.message)
  }
  return fieldErrors
}

export function extractErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    if ('detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (Array.isArray(detail)) {
        const humanized = humanizeDetailArray(detail)
        if (humanized) return humanized
      } else if (typeof detail === 'string') {
        return humanizePydanticDump(detail)
      }
    }
    if ('message' in body && typeof (body as { message: unknown }).message === 'string') {
      return humanizePydanticDump((body as { message: string }).message)
    }
  }
  return `Request failed with status ${status}`
}
