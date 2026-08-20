import type { SecurityGate, SecurityGateInput } from '../../domain/entities/security-gate-schema'

export interface SecurityGateRepository {
  list(): Promise<SecurityGate[]>
  create(input: SecurityGateInput): Promise<SecurityGate>
  update(id: string, input: SecurityGateInput): Promise<SecurityGate>
  remove(id: string): Promise<void>
}
