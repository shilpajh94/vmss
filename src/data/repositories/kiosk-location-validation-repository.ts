export interface KioskLocationValidationRepository {
  get(): Promise<boolean>
  set(enforce: boolean): Promise<boolean>
}
