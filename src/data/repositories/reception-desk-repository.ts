import type { ReceptionDesk, ReceptionDeskInput } from '../../domain/entities/reception-desk-schema'

export interface ReceptionDeskRepository {
  list(): Promise<ReceptionDesk[]>
  create(input: ReceptionDeskInput): Promise<ReceptionDesk>
  update(id: string, input: ReceptionDeskInput): Promise<ReceptionDesk>
  remove(id: string): Promise<void>
}
