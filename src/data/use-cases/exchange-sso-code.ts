import type { SsoAuthRepository } from '../repositories/sso-auth-repository'
import type { SsoExchangeResult } from '../../domain/entities/sso-exchange-schema'

export class ExchangeSsoCodeUseCase {
  private readonly ssoAuthRepository: SsoAuthRepository

  constructor(ssoAuthRepository: SsoAuthRepository) {
    this.ssoAuthRepository = ssoAuthRepository
  }

  async execute(code: string): Promise<SsoExchangeResult> {
    return this.ssoAuthRepository.exchange(code)
  }
}
