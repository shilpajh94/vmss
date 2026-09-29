import type {
  ListSecurityGatesPageParams,
  SecurityGateRepository,
  SecurityGatesPage,
} from '../repositories/security-gate-repository'

export class ListSecurityGatesPageUseCase {
  private readonly securityGateRepository: SecurityGateRepository

  constructor(securityGateRepository: SecurityGateRepository) {
    this.securityGateRepository = securityGateRepository
  }

  async execute(params: ListSecurityGatesPageParams): Promise<SecurityGatesPage> {
    return this.securityGateRepository.listPage(params)
  }
}
