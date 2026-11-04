export interface TenantSettingsRepository {
  getBadgePrintFlowEnabled(): Promise<boolean>
  setBadgePrintFlowEnabled(enabled: boolean): Promise<void>
  /** The tenant's zone access control switch (`zoneAccessEnabled`); while off, every zone route answers 404. */
  getZoneAccessEnabled(): Promise<boolean>
  setZoneAccessEnabled(enabled: boolean): Promise<void>
}
