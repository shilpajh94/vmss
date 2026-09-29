import type { VisitorPortalPageParams, VisitorPortalRepository } from '../repositories/visitor-portal-repository'
import type { VisitorPortalMe } from '../../domain/entities/visitor-portal-schema'

export class GetVisitorPortalMeUseCase {
  private readonly visitorPortalRepository: VisitorPortalRepository

  constructor(visitorPortalRepository: VisitorPortalRepository) {
    this.visitorPortalRepository = visitorPortalRepository
  }

  async execute(proofToken: string, page?: VisitorPortalPageParams): Promise<VisitorPortalMe> {
    return this.visitorPortalRepository.getMe(proofToken, page)
  }
}
