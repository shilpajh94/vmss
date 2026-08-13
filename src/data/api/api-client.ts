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
  parserSchema: ZodType<T>
}

interface UploadFileOptions<T> {
  endpointConfig: ApiEndpointDefinition
  file: File
  parserSchema: ZodType<T>
}

export class ApiClient {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
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

  async makeRequest<T>({ endpointConfig, body, queryParams, parserSchema }: MakeRequestOptions<T>): Promise<T> {
    const { endpoint, method, hasToken } = endpointConfig as EndpointConfigShape
    const url = `${this.baseUrl}${endpoint}${this.buildQueryString(queryParams)}`

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
}
