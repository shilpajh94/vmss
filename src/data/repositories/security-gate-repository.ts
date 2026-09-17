import type { SecurityGate, SecurityGateInput } from '../../domain/entities/security-gate-schema'

export interface ListSecurityGatesPageParams {
  page: number
  pageSize: number
  buildingId?: string
  gateType?: 'entry' | 'exit' | 'both'
  securityLevel?: 'standard' | 'high'
}

export interface SecurityGatesPage {
  items: SecurityGate[]
  total: number
}

export interface SecurityGateRepository {
  list(): Promise<SecurityGate[]>
  listPage(params: ListSecurityGatesPageParams): Promise<SecurityGatesPage>
  create(input: SecurityGateInput): Promise<SecurityGate>
  update(id: string, input: SecurityGateInput): Promise<SecurityGate>
  remove(id: string): Promise<void>
}
