import type { ZodType } from 'zod'
import { ApiError, extractErrorMessage, extractFieldErrors } from './api-error'
import type { ApiEndpointDefinition } from './api-endpoints'

// An array value is sent as a repeated key (`status=a&status=b`).
type QueryParams = Record<string, string | number | boolean | readonly string[] | undefined>

// ApiEndpointDefinition is `never` until API_ENDPOINTS has its first entry; this
// mirrors its shape so the request body below can read endpoint/method/hasToken.
interface EndpointConfigShape {
  endpoint: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  hasToken: boolean
}

interface MakeRequestOptions<T> {
  endpointConfig: ApiEndpointDefinition
  body?: unknown
  queryParams?: QueryParams
  pathParams?: Record<string, string>
  /** Extra request headers (e.g. `X-Branch-ID` for a branch-scoped call) merged in after the token/content-type ones. */
  headers?: Record<string, string>
  parserSchema: ZodType<T>
}

interface UploadFileOptions<T> {
  endpointConfig: ApiEndpointDefinition
  pathParams?: Record<string, string>
  file: File
  parserSchema: ZodType<T>
}

interface MultipartRequestOptions<T> {
  endpointConfig: ApiEndpointDefinition
  formData: FormData
  headers?: Record<string, string>
  parserSchema: ZodType<T>
}

interface DownloadFileOptions {
  endpointConfig: ApiEndpointDefinition
  queryParams?: QueryParams
  pathParams?: Record<string, string>
  /** Extra request headers (e.g. `Idempotency-Key`). */
  headers?: Record<string, string>
}

export const SESSION_EXPIRED_EVENT = 'auth:session-expired'

export class ApiClient {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  // A 401 on an endpoint that actually used the staff session token means
  // that token is dead — clear it and signal the app shell (via a plain
  // browser event, since `data/` cannot import `presentation/`) so a single
  // top-level listener can redirect to login, instead of letting the error
  // body fail Zod parsing with an unrelated-looking validation error.
  //
  // A 401 on a `hasToken: false` endpoint (e.g. the visitor-portal lookup,
  // gated by its own short-lived OTP proof token, not the staff session)
  // does NOT mean the staff session is dead — it must fall through to the
  // plain-error path below instead, or every expired visitor proof token
  // would incorrectly sign the staff session out.
  //
  // A 403 is different: the token is still valid, the caller just lacks
  // permission for this endpoint. Treating it the same as a 401 forces a
  // sign-out on a permission-gated route the user is otherwise legitimately
  // logged into — throw a plain error instead and let the caller's normal
  // error handling (load-failure message, toast, etc.) take over.
  //
  // Between the two: a `hasToken: false` endpoint that was still sent the
  // staff token (see `attachSessionToken`) and answered 401 has rejected that
  // token, so it is cleared — but the page may be a public one, so there is
  // no redirect; the request fails through the plain-error path.
  private handleAuthFailure(response: Response, hasToken: boolean, sentSessionToken: boolean): void {
    if (response.status === 401 && hasToken) {
      sessionStorage.removeItem('token')
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT))
      throw new ApiError('Session expired', response.status)
    }

    if (response.status === 401 && sentSessionToken) {
      sessionStorage.removeItem('token')
    }

    if (response.status === 403) {
      throw new ApiError('You do not have permission to perform this action', response.status)
    }
  }

  // 401 (hasToken)/403 get their own handling above; every other non-2xx
  // (400, 401 on a hasToken:false endpoint, 404, 422, 429, 500…) still
  // carries a JSON body, but it's an error shape, not the success schema —
  // parsing it with `parserSchema` would throw an opaque ZodError and bury
  // the backend's actual message. Surface that message instead, as an
  // `ApiError` so callers can still branch on the status.
  private async ensureOk(response: Response, hasToken: boolean, sentSessionToken: boolean): Promise<void> {
    this.handleAuthFailure(response, hasToken, sentSessionToken)
    if (response.ok) return

    const body: unknown = await response.json().catch(() => undefined)
    throw new ApiError(extractErrorMessage(body, response.status), response.status, extractFieldErrors(body))
  }

  // `hasToken: true` means the endpoint requires the staff session token;
  // `hasToken: false` only means it doesn't. The token is still sent whenever
  // a session exists, so endpoints that answer anonymous callers with less
  // (master-data lists, the employee directory) give a signed-in user the
  // full response. A caller-supplied `Authorization` (a visitor proof token)
  // is never overwritten. Returns whether the session token was attached.
  private attachSessionToken(headers: Record<string, string>, hasToken: boolean, endpoint: string): boolean {
    const token = sessionStorage.getItem('token')
    if (hasToken && !token) {
      throw new Error(`Missing auth token for endpoint: ${endpoint}`)
    }
    if (!token || 'Authorization' in headers) return false
    headers.Authorization = `Bearer ${token}`
    return true
  }

  // Exposed for adapters that need to build a full-page-navigation URL (e.g. an
  // SSO redirect) rather than issue a `fetch` through makeRequest.
  getBaseUrl(): string {
    return this.baseUrl
  }

  private buildPath(endpoint: string, pathParams?: Record<string, string>): string {
    if (!pathParams) return endpoint
    return endpoint.replace(/:([a-zA-Z]+)/g, (match, key: string) =>
      key in pathParams ? encodeURIComponent(pathParams[key]) : match,
    )
  }

  private buildQueryString(queryParams?: QueryParams): string {
    if (!queryParams) return ''

    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(queryParams)) {
      if (value === undefined) continue
      if (Array.isArray(value)) value.forEach((item: string) => params.append(key, item))
      else params.append(key, String(value))
    }

    const query = params.toString()
    return query ? `?${query}` : ''
  }

  async makeRequest<T>({ endpointConfig, body, queryParams, pathParams, headers: extraHeaders, parserSchema }: MakeRequestOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${this.buildPath(endpoint, pathParams)}${this.buildQueryString(queryParams)}`

    // Only set Content-Type when a body is actually sent — some backends (strict
    // JSON body parsers) try to parse the request body whenever this header is
    // present, and throw an unhandled 500 when it's empty (e.g. approveStep,
    // which has no body).
    const headers: Record<string, string> = {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...extraHeaders,
    }

    const sentSessionToken = this.attachSessionToken(headers, hasToken, endpoint)

    const response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    await this.ensureOk(response, hasToken, sentSessionToken)

    if (response.status === 204) {
      return parserSchema.parse(undefined)
    }

    return parserSchema.parse(await response.json())
  }

  // For endpoints that hand back a file (CSV/PDF export, etc.) rather than a JSON
  // body — plain browser navigation to these routes never attaches the
  // Authorization header, so the file must be fetched here and handed to the
  // caller as a Blob to save via an object URL instead.
  async downloadBlob({ endpointConfig, queryParams, pathParams, headers: extraHeaders }: DownloadFileOptions): Promise<Blob> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${this.buildPath(endpoint, pathParams)}${this.buildQueryString(queryParams)}`

    const headers: Record<string, string> = { ...extraHeaders }

    const sentSessionToken = this.attachSessionToken(headers, hasToken, endpoint)

    const response = await fetch(url, { method, headers })
    await this.ensureOk(response, hasToken, sentSessionToken)

    return response.blob()
  }

  async uploadFile<T>({ endpointConfig, pathParams, file, parserSchema }: UploadFileOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${this.buildPath(endpoint, pathParams)}`

    const headers: Record<string, string> = {}

    const sentSessionToken = this.attachSessionToken(headers, hasToken, endpoint)

    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(url, {
      method,
      headers,
      body: formData,
    })
    await this.ensureOk(response, hasToken, sentSessionToken)

    return parserSchema.parse(await response.json())
  }

  // For endpoints that mix a JSON-encoded field with raw file uploads in one
  // multipart/form-data body (e.g. a `payload` field alongside ID-proof files).
  async makeMultipartRequest<T>({ endpointConfig, formData, headers: extraHeaders, parserSchema }: MultipartRequestOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${endpoint}`

    const headers: Record<string, string> = { ...extraHeaders }

    const sentSessionToken = this.attachSessionToken(headers, hasToken, endpoint)

    const response = await fetch(url, {
      method,
      headers,
      body: formData,
    })
    await this.ensureOk(response, hasToken, sentSessionToken)

    return parserSchema.parse(await response.json())
  }
}
