export interface TenantSettingsRepository {
  getBadgePrintFlowEnabled(): Promise<boolean>
  setBadgePrintFlowEnabled(enabled: boolean): Promise<void>
  /** When false, a badge can be printed before the ID is verified (verification moves to check-in). */
  getBadgePrintRequiresIdVerification(): Promise<boolean>
  setBadgePrintRequiresIdVerification(required: boolean): Promise<void>
  /** The tenant's zone access control switch (`zoneAccessEnabled`); while off, every zone route answers 404. */
  getZoneAccessEnabled(): Promise<boolean>
  setZoneAccessEnabled(enabled: boolean): Promise<void>
}
