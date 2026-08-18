## 1. Notification system (`notifications` capability)

- [x] 1.1 Add `src/presentation/components/toast/toast-context.tsx`: `ToastProvider` (useReducer over `{ id, variant, message }[]`), `useToast()` returning `{ success, error, info }`, each scheduling its own auto-dismiss timer (4s success/info, 6s error) and clearing it on manual dismiss.
- [x] 1.2 Add `src/presentation/components/toast/Toast.tsx` and `ToastViewport.tsx`: stacked, dismissible toast rendering styled from design-theme tokens (`--color-success`, `--color-danger`, `--color-info`), with `role="alert"` for error and `role="status"` for success/info.
- [x] 1.3 Mount `ToastProvider` (rendering `ToastViewport`) in `src/App.tsx` alongside `AppDependenciesProvider`, above the router.

## 2. Async UI state components (`async-ui-states` capability)

- [x] 2.1 Add `src/presentation/components/ui/LoadingState.tsx`: takes an optional `label`, renders a centered spinner + label matching existing "Loading…" markup it replaces.
- [x] 2.2 Add `src/presentation/components/ui/EmptyState.tsx`: takes `message`, optional icon node, optional `action` (`{ label, onClick }`).

## 3. Retrofit staff-login

- [x] 3.1 In `use-staff-login-page.ts`, call `useToast().error(...)` in the SSO-initiation `catch` block alongside the existing `setErrorMessage`.

## 4. Retrofit staff-dashboard

- [x] 4.1 In `use-staff-dashboard.ts`, call `useToast().error(...)` in `loadDashboard`'s `catch` block, in addition to `setErrorMessage`.
- [x] 4.2 In `staff-dashboard.tsx`, replace the inline "Loading visit requests…" block with `LoadingState`.
- [x] 4.3 In `Components/KanbanColumn.tsx`, replace the inline `emptyMessage` text rendering with `EmptyState`.

## 5. Retrofit staff-audit-trail

- [x] 5.1 In `use-staff-audit-trail.ts`, call `useToast().error(...)` in `loadAuditTrail`'s `catch` block, in addition to `setErrorMessage`.
- [x] 5.2 In `staff-audit-trail.tsx` / `Components/ActivityTable.tsx`, replace inline loading and empty-log markup with `LoadingState` and `EmptyState`.

## 6. Retrofit staff-visitor-registration

- [x] 6.1 In `use-staff-visitor-registration-wizard.ts`, call `useToast().success(...)` on successful submission and `useToast().error(...)` on submission failure, alongside existing confirmation/error state.
- [x] 6.2 In the Review & Confirm step / submit handler, show `LoadingState` (or a busy submit button state) while submission is in flight.

## 7. Retrofit visitor-otp-verification

- [x] 7.1 In `use-visitor-otp.ts`'s `requestOtp`, call `useToast().error(...)` in the request `catch` block.
- [x] 7.2 In `use-visitor-otp.ts`'s `verifyOtp`, call `useToast().success(...)` on successful verification and `useToast().error(...)` in the verify `catch` block.
- [x] 7.3 In `Components/otp/OtpRequestScreen.tsx` and `OtpVerifyScreen.tsx`, replace any inline in-flight text with `LoadingState` where the step is submitting.

## 8. Retrofit visitor-track-request

- [x] 8.1 In `use-visitor-track-lookup.ts`, call `useToast().error(...)` in the lookup `catch` block, alongside the existing `errorMessage`.
- [x] 8.2 In `visitor-track.tsx`, replace any inline in-flight text with `LoadingState` while `status === 'loading'`.

## 9. Verification

- [x] 9.1 Run `npm run lint` and `tsc -b` (via `npm run build`) and fix any errors introduced by the retrofit.
- [x] 9.2 Exercised each retrofitted flow with a headless-browser smoke script (dev server + Playwright, no backend running so all calls fail — the error path): staff-login SSO failure, staff-dashboard load failure, staff-audit-trail load failure, OTP request failure, and track lookup failure all show their inline error plus a matching toast; dashboard/audit-trail also show `LoadingState` while loading. Caught and fixed a real bug in the process (see toast-context.tsx note below).
