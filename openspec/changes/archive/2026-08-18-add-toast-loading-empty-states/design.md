## Context

See proposal.md - Why. The project has zero UI dependencies beyond React/Tailwind (`package.json` has no component or toast library), and every existing UI primitive (`TextField`, `SelectField`, icons) is hand-rolled under `src/presentation/components/`. Every page hook (`use-staff-login-page.ts`, `use-staff-dashboard.ts`, `use-staff-audit-trail.ts`, `use-visitor-otp.ts`, `use-visitor-track-lookup.ts`, the visitor registration wizard hook) independently tracks `isLoading`/`status`/`errorMessage` and the page component renders its own inline "Loading…" text and error block. Per `.claude/rules/clean-architecture.md`, this is presentation-only work: no `data/`, `infrastructure/`, or `domain/` changes are needed since nothing here touches the network contract.

## Goals / Non-Goals

**Goals:**
- One `ToastProvider`/`useToast()` pair, mounted once, usable from any page hook or component without prop drilling.
- One `LoadingState` and one `EmptyState` component, used consistently instead of each page's bespoke markup.
- Retrofit the six existing pages identified in the proposal to call these, without changing their existing validation, navigation, or error-message behavior.

**Non-Goals:**
- No global/automatic error-toast wiring in `ApiClient` or use cases (per the "explicit per-page calls" decision) - `data/` and `infrastructure/` stay untouched.
- No toast queue persistence across navigations or page reloads.
- No new third-party toast/animation library - stays consistent with the project's zero-dependency UI approach.
- Not replacing the existing inline error messages (staff-login, audit trail, dashboard, OTP, track) - toasts are additive feedback, inline messages remain the durable, on-page state.

## Decisions

**Toast state: React Context + reducer in a single provider component, not a library.**
`ToastProvider` holds an array of `{ id, variant, message }` in `useReducer`, mounted in `src/App.tsx` alongside (not inside) `AppDependenciesProvider`, since toasts don't depend on app dependencies and both are pure presentation concerns. `useToast()` returns `{ success, error, info }` functions that dispatch `ADD`/`REMOVE`. Alternative considered: a third-party toast library (e.g. sonner) - rejected to keep the zero-dependency posture and because the design-theme tokens (`--color-success`, `--color-danger`, etc.) already give us the styling primitives a library would otherwise provide.

**Toast IDs and auto-dismiss timers use `crypto.randomUUID()` and `setTimeout`, not a global counter.**
Each `toast.*()` call generates an id via `crypto.randomUUID()` (available in all supported browsers) and schedules its own `setTimeout` (4s for success/info, 6s for error - errors get more reading time) that dispatches `REMOVE`; manual dismissal clears the timer and dispatches `REMOVE` immediately. This avoids a shared timer loop and keeps each toast independent.

**`LoadingState` and `EmptyState` are presentational components, not hooks.**
`LoadingState` takes an optional `label`; `EmptyState` takes `message`, an optional icon node, and an optional `action` (label + onClick). Pages keep owning their own `isLoading`/data-length checks and choose when to render which component - there is no shared "smart" wrapper that inspects a use case's return shape, since the six pages already have divergent loading/empty semantics (e.g. dashboard has per-column empty state, audit trail has one table-level empty state).

**Retrofit is additive to existing hook state, not a replacement.**
Each page hook keeps its existing `isLoading`/`errorMessage` state (the specs for staff-login, staff-dashboard, staff-audit-trail, staff-visitor-registration, visitor-otp-verification, and visitor-track-request still require the inline error message); the hook additionally calls `useToast()` inside the same `catch`/`then` blocks that already set that state. This satisfies the ADDED requirements in each capability's delta spec without touching a MODIFIED requirement or changing existing scenario outcomes.

## Risks / Trade-offs

- [Toast fires but the page unmounts immediately after (e.g. navigation on success)] → Acceptable: the toast viewport is mounted at the app root above the router, so it survives route changes and still displays/auto-dismisses normally.
- [Retrofitting six pages touches six hooks and their components in one change] → Mitigate by doing the shared components first and validating each page's build/lint independently in tasks.md, one page at a time, rather than one big-bang edit.
- [`crypto.randomUUID()` requires a secure context] → Non-issue: Vite dev server and the deployed app both run under HTTPS/localhost, which are secure contexts.
