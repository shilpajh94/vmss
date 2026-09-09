import type { ZodType } from 'zod'
import { extractErrorMessage } from './api-error'
import type { ApiEndpointDefinition } from './api-endpoints'

type QueryParams = Record<string, string | number | boolean | undefined>

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
  parserSchema: ZodType<T>
}

interface UploadFileOptions<T> {
  endpointConfig: ApiEndpointDefinition
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
}

export const SESSION_EXPIRED_EVENT = 'auth:session-expired'

export class ApiClient {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  // A 401 means the stored token is dead — clear it and signal the app shell
  // (via a plain browser event, since `data/` cannot import `presentation/`) so a
  // single top-level listener can redirect to login, instead of letting the error
  // body fail Zod parsing with an unrelated-looking validation error.
  //
  // A 403 is different: the token is still valid, the caller just lacks
  // permission for this endpoint. Treating it the same as a 401 forces a
  // sign-out on a permission-gated route the user is otherwise legitimately
  // logged into — throw a plain error instead and let the caller's normal
  // error handling (load-failure message, toast, etc.) take over.
  private handleAuthFailure(response: Response): void {
    if (response.status === 401) {
      sessionStorage.removeItem('token')
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT))
      throw new Error('Session expired')
    }

    if (response.status === 403) {
      throw new Error('You do not have permission to perform this action')
    }
  }

  // 401/403 get their own handling above; every other non-2xx (400, 404, 422, 500…)
  // still carries a JSON body, but it's an error shape, not the success schema —
  // parsing it with `parserSchema` would throw an opaque ZodError and bury the
  // backend's actual message. Surface that message instead.
  private async ensureOk(response: Response): Promise<void> {
    this.handleAuthFailure(response)
    if (response.ok) return

    const body: unknown = await response.json().catch(() => undefined)
    throw new Error(extractErrorMessage(body, response.status))
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
      if (value !== undefined) params.append(key, String(value))
    }

    const query = params.toString()
    return query ? `?${query}` : ''
  }

  async makeRequest<T>({ endpointConfig, body, queryParams, pathParams, parserSchema }: MakeRequestOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${this.buildPath(endpoint, pathParams)}${this.buildQueryString(queryParams)}`

    // Only set Content-Type when a body is actually sent — some backends (strict
    // JSON body parsers) try to parse the request body whenever this header is
    // present, and throw an unhandled 500 when it's empty (e.g. approveStep,
    // which has no body).
    const headers: Record<string, string> = body !== undefined ? { 'Content-Type': 'application/json' } : {}

    if (hasToken) {
      const token = sessionStorage.getItem('token')
      if (!token) {
        throw new Error(`Missing auth token for endpoint: ${endpoint}`)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    await this.ensureOk(response)

    if (response.status === 204) {
      return parserSchema.parse(undefined)
    }

    return parserSchema.parse(await response.json())
  }

  // For endpoints that hand back a file (CSV/PDF export, etc.) rather than a JSON
  // body — plain browser navigation to these routes never attaches the
  // Authorization header, so the file must be fetched here and handed to the
  // caller as a Blob to save via an object URL instead.
  async downloadBlob({ endpointConfig, queryParams, pathParams }: DownloadFileOptions): Promise<Blob> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${this.buildPath(endpoint, pathParams)}${this.buildQueryString(queryParams)}`

    const headers: Record<string, string> = {}

    if (hasToken) {
      const token = sessionStorage.getItem('token')
      if (!token) {
        throw new Error(`Missing auth token for endpoint: ${endpoint}`)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(url, { method, headers })
    await this.ensureOk(response)

    return response.blob()
  }

  async uploadFile<T>({ endpointConfig, file, parserSchema }: UploadFileOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${endpoint}`

    const headers: Record<string, string> = {}

    if (hasToken) {
      const token = sessionStorage.getItem('token')
      if (!token) {
        throw new Error(`Missing auth token for endpoint: ${endpoint}`)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(url, {
      method,
      headers,
      body: formData,
    })
    await this.ensureOk(response)

    return parserSchema.parse(await response.json())
  }

  // For endpoints that mix a JSON-encoded field with raw file uploads in one
  // multipart/form-data body (e.g. a `payload` field alongside ID-proof files).
  async makeMultipartRequest<T>({ endpointConfig, formData, headers: extraHeaders, parserSchema }: MultipartRequestOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${endpoint}`

    const headers: Record<string, string> = { ...extraHeaders }

    if (hasToken) {
      const token = sessionStorage.getItem('token')
      if (!token) {
        throw new Error(`Missing auth token for endpoint: ${endpoint}`)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(url, {
      method,
      headers,
      body: formData,
    })
    await this.ensureOk(response)

    return parserSchema.parse(await response.json())
  }
}
