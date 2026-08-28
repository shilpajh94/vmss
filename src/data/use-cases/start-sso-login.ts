import type { SsoAuthRepository } from '../repositories/sso-auth-repository'

export class StartSsoLoginUseCase {
  private readonly ssoAuthRepository: SsoAuthRepository
  private readonly tenantSlug: string

  constructor(ssoAuthRepository: SsoAuthRepository, tenantSlug: string) {
    this.ssoAuthRepository = ssoAuthRepository
    this.tenantSlug = tenantSlug
  }

  execute(): string {
    return this.ssoAuthRepository.startLoginUrl(this.tenantSlug)
  }
}
