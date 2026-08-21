import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { VisitorOtpRepository } from '../data/repositories/visitor-otp-repository'
import type { OtpChannel } from '../domain/entities/visitor-otp-request-schema'
import { VisitorOtpRequestResponseSchema, type VisitorOtpRequest, type VisitorOtpRequestResponse } from '../domain/entities/visitor-otp-request-schema'
import { VisitorOtpVerifyResponseSchema, type VisitorOtpVerify, type VisitorOtpVerifyResponse } from '../domain/entities/visitor-otp-verify-schema'

// The UI only collects one free-text contact field; the API needs to know
// which delivery channel it maps to (identity-verification/schemas.py's
// email/sms/whatsapp Channel enum). WhatsApp has no UI entry point yet.
function resolveOtpChannel(contact: string): OtpChannel {
  return contact.includes('@') ? 'email' : 'sms'
}

export class HttpVisitorOtpRepository implements VisitorOtpRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async requestOtp(request: VisitorOtpRequest): Promise<VisitorOtpRequestResponse> {
    return this.apiClient.makeRequest<VisitorOtpRequestResponse>({
      endpointConfig: API_ENDPOINTS.REQUEST_VISITOR_OTP,
      body: { identifier: request.contact, channel: resolveOtpChannel(request.contact) },
      parserSchema: VisitorOtpRequestResponseSchema,
    })
  }

  async verifyOtp(request: VisitorOtpVerify): Promise<VisitorOtpVerifyResponse> {
    return this.apiClient.makeRequest<VisitorOtpVerifyResponse>({
      endpointConfig: API_ENDPOINTS.VERIFY_VISITOR_OTP,
      body: {
        identifier: request.contact,
        channel: resolveOtpChannel(request.contact),
        code: request.code,
      },
      parserSchema: VisitorOtpVerifyResponseSchema,
    })
  }
}
