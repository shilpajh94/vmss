export interface TenantSettingsRepository {
  getBadgePrintFlowEnabled(): Promise<boolean>
  setBadgePrintFlowEnabled(enabled: boolean): Promise<void>
}
