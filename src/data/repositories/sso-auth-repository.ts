import type { SsoExchangeResult } from '../../domain/entities/sso-exchange-schema'

export interface SsoAuthRepository {
  startLoginUrl(tenantSlug: string): string
  exchange(code: string): Promise<SsoExchangeResult>
}
