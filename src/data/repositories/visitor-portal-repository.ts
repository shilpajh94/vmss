import type { VisitorPortalMe } from '../../domain/entities/visitor-portal-schema'

export interface VisitorPortalPageParams {
  page: number
  pageSize: number
}

export interface VisitorPortalRepository {
  getMe(proofToken: string, page?: VisitorPortalPageParams): Promise<VisitorPortalMe>
}
