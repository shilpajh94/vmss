import type { BadgeScanResult, CheckinSearchPage, CheckinSearchRow } from '../../domain/entities/checkin-schema'

export interface CheckinRepository {
  search(params: { q: string; page: number; pageSize: number }): Promise<CheckinSearchPage>
  verifyId(visitId: string): Promise<void>
  /** Captures a photo for a visit that has none; returns the refreshed row. */
  uploadPhoto(visitId: string, file: File): Promise<CheckinSearchRow>
  /** Returns the badge PDF. `idempotencyKey` is reused by the caller for retries. */
  printBadge(visitId: string, idempotencyKey: string): Promise<Blob>
  /** Invalidates the previous badge; only call from a confirmed user action. */
  reprintBadge(visitId: string, reason: string): Promise<Blob>
  checkOutWithBadge(token: string): Promise<BadgeScanResult>
  checkInWithBadge(token: string): Promise<BadgeScanResult>
  reEnterWithBadge(token: string): Promise<BadgeScanResult>
}
