import type { ZodType } from 'zod'
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

export class ApiClient {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
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

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

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

    if (response.status === 204) {
      return parserSchema.parse(undefined)
    }

    return parserSchema.parse(await response.json())
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

    return parserSchema.parse(await response.json())
  }
}
