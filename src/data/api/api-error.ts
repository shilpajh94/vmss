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

const PYDANTIC_ISSUE_PATTERN = /^([\w.]+)\n\s+(.+?)\s*\[type=[^\]]*\]\s*$/gm

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
    issues.push(`${describeFieldPath(match[1])}: ${match[2].trim()}`)
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
      const msg = typeof item.msg === 'string' ? item.msg : undefined
      if (!msg) return undefined
      const loc = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : undefined
      return loc ? `${describeFieldPath(loc)}: ${msg}` : msg
    })
    .filter((issue): issue is string => Boolean(issue))
  return issues.length > 0 ? issues.join(' ') : undefined
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
