## 1. Data layer

- [x] 1.1 Add `badgePrintRequiresIdVerification` (optional, default `true`) to the tenant read and settings schemas in `checkin-schema.ts`
- [x] 1.2 Extend `TenantSettingsRepository` and `HttpTenantSettingsRepository` with get/set for the new setting (PATCH body only the one field)
- [x] 1.3 Add `GetBadgePrintRequiresIdVerificationUseCase` and `SetBadgePrintRequiresIdVerificationUseCase`; wire in `composition-root.ts` and `AppDependencies`

## 2. Admin toggle

- [x] 2.1 Extend `useBadgePrintFlowSetting` with load/change for the new setting (optimistic, revert and toast on failure)
- [x] 2.2 Add "Require ID verification before printing badge" `ToggleSwitch` to `BadgePrintFlowCard`, disabled with helper text while badge printing is off; hidden without `tenants:update`

## 3. Reception screen

- [x] 3.1 Relabel the unverified indicator in `BadgeResultRow` to "ID pending" with neutral styling; keep the "ID verified" action while pending
- [x] 3.2 Confirm Print is not disabled by `idVerifiedAt` and the `id_not_verified` 409 copy in `describePrintError` still applies

## 4. Badge-scan check-in

- [x] 4.1 Add `isIdNotVerifiedError` to `badge-print-errors.ts`
- [x] 4.2 Add an `id-required` outcome to `useBadgeScan` for the check-in action and render the "ID verification required, see reception" message in `badge-scan.tsx`; no auto-retry
- [x] 4.3 Add an optional Verify ID prompt (calls `VerifyCheckinIdUseCase`, then offers an explicit one-time retry) that renders only when a visit id is available; check-out and re-enter paths unchanged

## 5. Verification

- [x] 5.1 Unit tests: schema default, admin toggle (load, save, revert, disabled when flow off), `isIdNotVerifiedError`, scan 409 handling, "ID pending" label
- [x] 5.2 Run lint, type-check and the test suite
