import type { VisitorOtpRepository } from '../repositories/visitor-otp-repository'
import type { VisitorOtpVerify, VisitorOtpVerifyResponse } from '../../domain/entities/visitor-otp-verify-schema'

export class VerifyVisitorOtpUseCase {
  private readonly visitorOtpRepository: VisitorOtpRepository

  constructor(visitorOtpRepository: VisitorOtpRepository) {
    this.visitorOtpRepository = visitorOtpRepository
  }

  async execute(request: VisitorOtpVerify): Promise<VisitorOtpVerifyResponse> {
    return this.visitorOtpRepository.verifyOtp(request)
  }
}
