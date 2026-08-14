import type { VisitorOtpRepository } from '../repositories/visitor-otp-repository'
import type { VisitorOtpRequest, VisitorOtpRequestResponse } from '../../domain/entities/visitor-otp-request-schema'

export class RequestVisitorOtpUseCase {
  private readonly visitorOtpRepository: VisitorOtpRepository

  constructor(visitorOtpRepository: VisitorOtpRepository) {
    this.visitorOtpRepository = visitorOtpRepository
  }

  async execute(request: VisitorOtpRequest): Promise<VisitorOtpRequestResponse> {
    return this.visitorOtpRepository.requestOtp(request)
  }
}
