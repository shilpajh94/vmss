import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitorOtpRepository } from '../data/repositories/visitor-otp-repository'
import { VisitorOtpRequestResponseSchema, type VisitorOtpRequest, type VisitorOtpRequestResponse } from '../domain/entities/visitor-otp-request-schema'
import { VisitorOtpVerifyResponseSchema, type VisitorOtpVerify, type VisitorOtpVerifyResponse } from '../domain/entities/visitor-otp-verify-schema'

export class HttpVisitorOtpRepository implements VisitorOtpRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async requestOtp(request: VisitorOtpRequest): Promise<VisitorOtpRequestResponse> {
    return this.apiClient.makeRequest<VisitorOtpRequestResponse>({
      endpointConfig: API_ENDPOINTS.REQUEST_VISITOR_OTP,
      body: request,
      parserSchema: VisitorOtpRequestResponseSchema,
    })
  }

  async verifyOtp(request: VisitorOtpVerify): Promise<VisitorOtpVerifyResponse> {
    return this.apiClient.makeRequest<VisitorOtpVerifyResponse>({
      endpointConfig: API_ENDPOINTS.VERIFY_VISITOR_OTP,
      body: request,
      parserSchema: VisitorOtpVerifyResponseSchema,
    })
  }
}
