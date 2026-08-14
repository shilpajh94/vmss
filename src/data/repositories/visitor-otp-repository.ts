import type { VisitorOtpRequest, VisitorOtpRequestResponse } from '../../domain/entities/visitor-otp-request-schema'
import type { VisitorOtpVerify, VisitorOtpVerifyResponse } from '../../domain/entities/visitor-otp-verify-schema'

export interface VisitorOtpRepository {
  requestOtp(request: VisitorOtpRequest): Promise<VisitorOtpRequestResponse>
  verifyOtp(request: VisitorOtpVerify): Promise<VisitorOtpVerifyResponse>
}
