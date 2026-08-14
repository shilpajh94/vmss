## Context

The app is a Vite + React 19 + TypeScript SPA following the layered architecture in `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md`: `presentation → data → domain`, with `infrastructure` implementing `data/repositories` ports via `ApiClient`, all wired lazily in `composition-root.ts`. Existing features (visitor request, OTP verification, tracking) follow this pattern end-to-end. There is currently no staff-facing area, no auth repository, and no session/token handling beyond the `hasToken` support already built into `ApiClient`/`API_ENDPOINTS`.

The Figma source (`staff-sso-login`, node `30:4`) is SSO-only: one "Sign in with SSO" button, no credential fields. Per user decision, this change wires that button end to end against a placeholder backend contract (`INITIATE_STAFF_SSO`), not a full OIDC redirect+callback exchange, and lands the user on a new placeholder `/staff/dashboard` route. See proposal.md - Why / What Changes.

## Goals / Non-Goals

**Goals:**
- Pixel-match the Figma "Enterprise Sign In" screen at `/staff/login`, including the dark Staff Gateway header, SSO card, and footer.
- Wire the "Sign in with SSO" button through the full ports-and-adapters chain (`API_ENDPOINTS` → `ApiClient` → repository port → adapter → use case → hook) so a real backend can be dropped in later by only changing the endpoint contract/response shape.
- Provide a minimal placeholder `/staff/dashboard` route so the redirect target exists.

**Non-Goals:**
- Implementing the real identity provider integration, OAuth/OIDC callback handling, code-for-token exchange, or session/token storage for staff. The initiation endpoint and response schema here are placeholders to be revisited once the backend team defines the actual SSO contract.
- Building out real staff dashboard functionality (navigation, data, permissions) — the dashboard page is a landing placeholder only.
- Any change to visitor-facing routes, components, or specs.

## Decisions

**New capability, not an extension of an existing one.** `staff-login` is unrelated in behavior to visitor OTP/request/tracking capabilities, so it gets its own spec file and its own presentation/data/infrastructure surface rather than being folded into an existing one.

**Own header component, not `PortalHeader` reuse.** `PortalHeader` (`src/presentation/components/PortalHeader.tsx`) is light-themed and visitor-branded. The Figma staff header is dark, has a different badge and a system-status indicator, and per spec must not reuse the visitor header. Decision: add a page-scoped `StaffGatewayHeader` component under `src/presentation/pages/staff-login/Components/`, not a shared component — it isn't reused elsewhere yet. Promote to `src/presentation/components/` only if a second staff screen needs it.

**Placeholder API contract, following the existing repo pattern exactly.**
- `API_ENDPOINTS.INITIATE_STAFF_SSO`: `{ endpoint: "/staff-auth/sso/initiate", method: "POST", hasToken: false }` — mirrors how `REQUEST_VISITOR_OTP` etc. are declared.
- Domain schema `src/domain/entities/staff-sso-initiate-schema.ts`: `StaffSsoInitiateResponseSchema = z.object({ redirectUrl: z.string() })`, `type StaffSsoInitiateResponse = z.infer<...>`.
- Port `src/data/repositories/staff-auth-repository.ts`: `interface StaffAuthRepository { initiateSso(): Promise<StaffSsoInitiateResponse> }`.
- Adapter `src/infrastructure/staff-auth-repository.ts`: `HttpStaffAuthRepository implements StaffAuthRepository`, calls `apiClient.makeRequest({ endpointConfig: API_ENDPOINTS.INITIATE_STAFF_SSO, parserSchema: StaffSsoInitiateResponseSchema })`.
- Use case `src/data/use-cases/initiate-staff-sso.ts`: `InitiateStaffSsoUseCase`, constructor-injected `StaffAuthRepository`, `execute()` delegates to the port.
- Composition root: lazy `resolveStaffAuthRepository` → `resolveInitiateStaffSsoUseCase`, both exposed on `AppDependencies`.

This keeps the whole chain swappable later: once the real IdP contract exists, only the endpoint path/method and the response schema need to change — the port, use case, and hook shape stay stable.

**Navigation on success uses a full browser redirect (`window.location.assign`), not client-side router navigation.** An SSO redirect URL points to an external identity provider, not an internal route, so React Router's `navigate()` is the wrong tool here. The page hook calls `window.location.assign(redirectUrl)` after a successful `initiateSso()` call.

**`/staff/dashboard` is a static placeholder page**, no props, no use case, added directly to `src/App.tsx`'s `<Routes>` alongside `/staff/login`. It exists purely so the redirect target resolves; it is not wired to any real session/auth-guard logic since none exists yet (Non-Goals).

## Risks / Trade-offs

- **[Backend contract doesn't exist yet]** → The `INITIATE_STAFF_SSO` endpoint and `redirectUrl` response shape are assumptions. Mitigation: isolate them behind the `StaffAuthRepository` port so only the adapter and schema need to change when the real contract lands; the use case and UI are unaffected.
- **[No auth guard on `/staff/dashboard`]** → Anyone can navigate to it directly today. Mitigation: acceptable for this change per Non-Goals; flagged here so a follow-up change adds route protection once real session handling exists.
- **[Page-scoped header duplicates some visual patterns from `PortalHeader`]** → Minor duplication (brand mark rendering) between `StaffGatewayHeader` and `PortalHeader`. Mitigation: acceptable now given the visual designs diverge significantly (dark vs. light, different content); revisit extraction if a third header variant appears.

## Open Questions

- What the real SSO identity provider is and its exact initiation/callback contract — deferred to a future change once the backend team finalizes it; does not change this change's specs or approach.
