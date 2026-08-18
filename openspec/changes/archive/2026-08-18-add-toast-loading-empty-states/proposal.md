## Why

Every page in the app (staff login, OTP verification, staff dashboard, visitor registration, audit trail, visitor request/track) currently manages loading, error, and empty conditions with its own ad-hoc `isLoading`/`errorMessage` state and hand-rolled markup (e.g. `use-staff-dashboard.ts`, `use-staff-audit-trail.ts`). There is no shared toast/notification mechanism at all — transient success/failure feedback (e.g. "visitor registered", "sign-in failed") has nowhere to go except inline error text that persists until the next action. This produces inconsistent UX (each page's loading/empty copy and layout differs) and duplicated logic. This change introduces a shared toast system and shared loading/empty-state UI, then retrofits existing pages onto it.

## What Changes

- Add a `ToastProvider` + `useToast()` hook exposing `toast.success(message)`, `toast.error(message)`, and `toast.info(message)`, mounted once at the app root above the router.
- Add a `ToastViewport`/`Toast` presentation component (stacked, auto-dismissing, dismissible, accessible via `role="status"`/`role="alert"`) styled from the existing design-theme tokens.
- Add a reusable `Spinner`/`LoadingState` component for in-progress async operations, replacing inline "Loading…" text blocks.
- Add a reusable `EmptyState` component (icon/message/optional action) for lists and collections with zero results, replacing inline empty-message text (e.g. dashboard Kanban columns, audit trail table, visitor lists).
- Retrofit existing page hooks/components to use the new components:
  - `staff-login`: error toast on failed SSO initiation.
  - `visitor-request` (OTP steps + wizard steps): success/error toasts for OTP request/verify and submission steps; `LoadingState` during in-flight calls.
  - `staff-dashboard`: `LoadingState` while loading, `EmptyState` per empty Kanban column, error toast on load/refresh failure (in addition to existing retry affordance).
  - `staff-visitor-registration`: success toast on registration submit, error toast on failure, `LoadingState` during submission.
  - `staff-audit-trail`: `LoadingState` while loading, `EmptyState` when the filtered result set is empty, error toast on load failure.
  - `visitor-track`: `LoadingState` during lookup, error toast alongside existing inline not-found message.
- No changes to `data/`, `infrastructure/`, or `domain/` — this is presentation-only.

## Capabilities

### New Capabilities
- `notifications`: toast/notification system — provider, hook, and rendered toast UI for transient success/error/info feedback triggered explicitly by pages.
- `async-ui-states`: shared loading and empty-state presentation components used across pages for in-progress and zero-result conditions.

### Modified Capabilities
- `staff-login`: adds error toast on failed SSO initiation, in addition to existing inline error message.
- `staff-dashboard`: adds shared loading/empty-state components and error toast; behavior of what counts as loading/empty is unchanged, only presentation.
- `staff-audit-trail`: adds shared loading/empty-state components and error toast; behavior unchanged, only presentation.
- `staff-visitor-registration`: adds success/error toasts and shared loading indicator during submission.
- `visitor-otp-verification`: adds success/error toasts for OTP request/verify.
- `visitor-track-request`: adds error toast and shared loading indicator during lookup.

## Impact

- New shared components under `src/presentation/components/` (toast provider/hook/viewport, `Spinner`/`LoadingState`, `EmptyState`).
- App root (`src/App.tsx`) gains a `ToastProvider` mounted alongside `AppDependenciesProvider`.
- Existing page hooks (`use-staff-login-page.ts`, `use-staff-dashboard.ts`, `use-staff-audit-trail.ts`, `use-visitor-otp.ts`, `use-visitor-track-lookup.ts`, visitor registration wizard hook) call `useToast()` to fire notifications alongside their existing state.
- Existing page components (`staff-dashboard.tsx`, `KanbanColumn.tsx`, audit trail page/table, visitor track page) swap inline loading/empty markup for the new shared components.
- No API, schema, endpoint, or use-case changes; purely additive presentation-layer work plus non-behavioral rewiring of existing pages.
