## Context

See proposal.md - Why. This backend now exposes three SSO endpoints (confirmed via the live dev backend's `/openapi.json` at `https://vmss-new-api.ddev.site:8443/openapi.json`):

- `GET /api/v1/auth/sso/{tenant_slug}/login` — public, unauthenticated, redirects the browser to the tenant's configured IdP. Rate-limited 3/min per IP.
- `GET /api/v1/auth/sso/callback?code&state` — public, the IdP's return redirect target. Always 3xx-redirects (no JSON response); this is a **backend** route, not a frontend one — the browser hits it directly after the IdP round trip, and the backend then redirects the browser onward to the frontend.
- `POST /api/v1/auth/sso/exchange` — public, body `{ code: string }` (`SsoExchangeRequest`), response `Envelope<TokenResponse>` = `{ success, message, data: { accessToken, refreshToken, tokenType } }` — same envelope shape the existing password-login flow already unwraps (see `staff-password-login`'s design.md). Trades a short-lived, single-use exchange code for the real token pair.

The codebase already establishes the layering this change must follow (`.claude/rules/clean-architecture.md`, `.claude/rules/data-api-layer.md`): `API_ENDPOINTS` entry → Zod schema in `domain/entities` → port in `data/repositories` → adapter in `infrastructure` → use case in `data/use-cases` → wiring in `composition-root.ts` → hook in `presentation/pages/staff-sso-login/hooks` → component. The bearer-token contract is already fixed by `ApiClient`: `hasToken: true` reads `sessionStorage.getItem("token")`; login-family endpoints are `hasToken: false`.

The existing `/admin/login` page (folder `staff-login`) already implements the exact chrome the Figma "staff-sso-login" design (node 30:14) reuses: full-bleed hero image, dark gateway header (`VisitorPass` + badge + status dot), a white centered card, a "Need help? Contact System Administrator" link below the card, and a footer with copyright/policy links. Per explicit user decision, that folder is left untouched; the new screen gets its own `staff-sso-login` folder and duplicates the small amount of matching chrome rather than extracting a shared component now.

## Goals / Non-Goals

**Goals:**
- Implement the full three-leg SSO flow (start → IdP → callback → exchange) behind a single `/staff/login` route/screen, matching the Figma design's single-card layout.
- Keep the existing session contract: after a successful exchange, `sessionStorage["token"]` is set so all existing `hasToken: true` requests keep working unchanged.
- Re-point staff-only guard redirects (`staff-dashboard`, `staff-audit-trail`, `staff-visitor-registration`) at `/staff/login`, per the modified `staff-login` spec delta.

**Non-Goals:**
- Multi-tenant tenant picking in the UI — this deployment is single-tenant (one `VITE_SSO_TENANT_SLUG`), matching the existing single-`VITE_API_BASE_URL` deployment model. A tenant-selector UI is out of scope.
- Changing `/admin/login`, its password flow, or admin-only guard redirects — explicitly out of scope per user decision.
- Token refresh, "remember me", or SSO config management (`GET/PUT /auth/sso/config`, role mappings) — those are backend/admin-config concerns, not this staff-facing screen.
- Handling the backend's `GET /api/v1/auth/sso/callback` route itself — that endpoint lives on the backend and is never called directly by frontend code; the frontend only reacts to where the backend redirects the browser afterward.

## Decisions

- **Tenant slug via env var**: add `VITE_SSO_TENANT_SLUG` to `.env.example` / `import.meta.env`, read it in the composition root the same way `VITE_API_BASE_URL` is read. Alternative considered: let the user type a tenant slug — rejected because the Figma design shows no such field, and the rest of this app already assumes one tenant per deployment (no tenant list/switcher exists anywhere in the frontend).
- **`START_SSO_LOGIN` is a full-page navigation, not a `fetch`**: `window.location.assign(...)` to `${VITE_API_BASE_URL}/auth/sso/${tenantSlug}/login`, built directly rather than through `ApiClient.makeRequest` — the browser must follow the backend's redirect chain to the external IdP, which `fetch` cannot do for a top-level navigation. This mirrors how the original 2026-08-14 SSO implementation invoked `window.location.assign(redirectUrl)`.
- **`/staff/login` doubles as the callback landing screen**: the Figma design shows one screen, not a separate "processing" screen, and the existing app has no dedicated non-login route to receive a mid-flow redirect. The screen reads a completion code from its own URL (`useSearchParams`) on mount; if present, it immediately shows a loading state and calls the exchange use case instead of the idle "Sign in with SSO" card state. Alternative considered: a dedicated `/staff/login/callback` route — rejected as unnecessary indirection when the same component can branch on a query param, consistent with the single-card design.
- **Exchange code query param name — assumption to verify against the live dev backend**: the backend's own `GET /auth/sso/callback` docstring only says it "3xx-redirects" without documenting its target URL or param name. This design assumes the backend redirects to the frontend's `/staff/login` with a `?code=<value>` query parameter (matching `SsoExchangeRequest.code`'s field name), the same pattern the callback endpoint itself receives from the IdP. Implementation must confirm this against the running dev backend (same discovery approach `staff-password-login`'s design.md used for its request/response contract) before finalizing the query-param name and, if it differs, adjust the hook accordingly — this does not change the requirement, approach, or task breakdown, only a literal string.
- **New port `SsoAuthRepository`** rather than extending `StaffAuthRepository`: SSO's `startLogin`/`exchange` operations are unauthenticated and structurally unrelated to `StaffAuthRepository.login()`/`getCurrentUser()` (which stay as-is, serving `/admin/login`). Keeping them separate avoids coupling the untouched password-login port to new SSO concerns.
- **New use cases**: `StartSsoLoginUseCase` (builds/navigates to the IdP redirect URL) and `ExchangeSsoCodeUseCase` (calls `POST /auth/sso/exchange`, returns `{ token: string }` unwrapped from the envelope — mirroring how `LoginStaffUseCase` already unwraps `TokenResponse`).
- **Token write location**: the SSO hook (`use-staff-sso-login-page.ts`) calls `sessionStorage.setItem('token', token)` directly after a successful exchange, matching the existing direct-read/write pattern every staff/admin hook already uses (per `staff-password-login`'s design.md - Decisions; not introducing a session-repository abstraction here either).
- **New icon assets**: the Figma design uses a key icon (SSO button) and a shield icon (security note) that don't exist in `src/assets/`. Add `key.svg` / `shield.svg` and export them from the `src/assets/icons.ts` barrel, per the existing icon convention.

## Risks / Trade-offs

- [Exchange code query-param name is assumed, not confirmed] → Flagged above as a Decision to verify against the live dev backend during implementation; low blast radius (one literal string in one hook).
- [BREAKING: staff lose the password-login fallback at `/admin/login`] → Called out as **BREAKING** in proposal.md; acceptable per explicit user confirmation, since SSO is now the intended staff entry point and admin keeps its own working path.
- [Rate limiting (3/min per IP) on `start_login` and `exchange`] → A shared office IP could exhaust the limit across concurrent staff sign-ins; no mitigation in this change (matches the backend's existing rate-limit behavior on `POST /auth/login`, which has the same constraint today).

## Migration Plan

1. Add `VITE_SSO_TENANT_SLUG` to `.env.example`; add `START_SSO_LOGIN` / `SSO_EXCHANGE` to `API_ENDPOINTS`; add `sso-exchange-schema.ts` (domain); add `SsoAuthRepository` port, `HttpSsoAuthRepository` adapter, `StartSsoLoginUseCase` / `ExchangeSsoCodeUseCase` use cases; wire them in `composition-root.ts`.
2. Build the `staff-sso-login` page, hook, and components (card, key/shield icons), reusing the hero/header/footer visual pattern from the existing `staff-login` page without importing from it.
3. Add the `/staff/login` route in `src/App.tsx`.
4. Update the three staff-only guard redirects (`use-staff-dashboard.ts`, `use-staff-audit-trail.ts`, `staff-visitor-registration.tsx`) from `/admin/login` to `/staff/login`.
5. Manually verify the full round trip against the live dev backend (start → IdP → callback → exchange) to confirm the callback's redirect target and query-param name; adjust the hook's param name if needed.

No data migration or rollback concerns: this is a stateless UI/API-integration addition with no persisted data, alongside a literal-string change in a handful of existing guard redirects.
