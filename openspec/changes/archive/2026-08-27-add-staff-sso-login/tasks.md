## 1. Config & endpoints

- [x] 1.1 Add `VITE_SSO_TENANT_SLUG` to `.env.example`
- [x] 1.2 Add `START_SSO_LOGIN` (`GET /auth/sso/:tenantSlug/login`, `hasToken: false`) and `SSO_EXCHANGE` (`POST /auth/sso/exchange`, `hasToken: false`) to `API_ENDPOINTS` in `src/data/api/api-endpoints.ts`

## 2. Domain schema

- [x] 2.1 Add `src/domain/entities/sso-exchange-schema.ts`: `SsoExchangeRequestSchema` (`{ code: string }`), `SsoExchangeResponseSchema` for the `Envelope<TokenResponse>` shape (`{ success, message, data: { accessToken, refreshToken, tokenType } }`), and inferred types

## 3. Port, adapter, use cases

- [x] 3.1 Add `SsoAuthRepository` port in `src/data/repositories/sso-auth-repository.ts` with `startLoginUrl(tenantSlug): string` and `exchange(code): Promise<SsoExchangeResponse>`
- [x] 3.2 Implement `HttpSsoAuthRepository` in `src/infrastructure/sso-auth-repository.ts`: `startLoginUrl` builds the full `${baseUrl}/auth/sso/{tenantSlug}/login` URL; `exchange` calls `ApiClient.makeRequest` with `API_ENDPOINTS.SSO_EXCHANGE` and `SsoExchangeResponseSchema`
- [x] 3.3 Add `StartSsoLoginUseCase` in `src/data/use-cases/start-sso-login.ts` — returns the redirect URL for the configured tenant slug
- [x] 3.4 Add `ExchangeSsoCodeUseCase` in `src/data/use-cases/exchange-sso-code.ts` — calls the port and returns `{ token: string }` unwrapped from `data.accessToken`

## 4. Composition root

- [x] 4.1 Read `VITE_SSO_TENANT_SLUG` in `composition-root.ts`
- [x] 4.2 Add lazy resolvers for `SsoAuthRepository` → `startSsoLoginUseCase` / `exchangeSsoCodeUseCase`, and expose both on `AppDependencies`

## 5. Icons

- [x] 5.1 Add `key.svg` and `shield.svg` to `src/assets/` and export `KeyIcon` / `ShieldIcon` from `src/assets/icons.ts`

## 6. Staff SSO login page

- [x] 6.1 Create `src/presentation/pages/staff-sso-login/hooks/use-staff-sso-login-page.ts`: on mount, read a `code` search param; if present, set a "completing sign-in" status and call `exchangeSsoCodeUseCase`, on success write `sessionStorage["token"]` and navigate to `/staff/dashboard`, on failure set an inline error and fire an error toast; expose a `startSso()` action that calls `startSsoLoginUseCase` and does `window.location.assign(url)`
- [x] 6.2 Create the SSO card component: "STAFF PORTAL" tag, "Enterprise Sign In" title, "Sign in with your organization credentials" description, "Sign in with SSO" button (key icon) wired to `startSso()`, "Secured by corporate multi-factor authentication" note (shield icon); button shows a loading/disabled state while completing sign-in and an inline error message on failure
- [x] 6.3 Create `src/presentation/pages/staff-sso-login/staff-sso-login.tsx`: hero image background, gateway header (badge text "STAFF PORTAL"), the SSO card, the "Need help? Contact System Administrator" link, and footer — matching the existing `staff-login` page's layout structure without importing from it
- [x] 6.4 Register the `/staff/login` route in `src/App.tsx`

## 7. Guard redirects

- [x] 7.1 Update `src/presentation/pages/staff-dashboard/hooks/use-staff-dashboard.ts` guard redirects from `/admin/login` to `/staff/login`
- [x] 7.2 Update `src/presentation/pages/staff-audit-trail/hooks/use-staff-audit-trail.ts` guard redirects from `/admin/login` to `/staff/login`
- [x] 7.3 Update `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx` guard redirects from `/admin/login` to `/staff/login`

## 8. Verification

- [x] 8.1 Run the full SSO round trip against the live dev backend (`https://vmss-new-api.ddev.site:8443`); confirm the callback's redirect target and query-param name match the `code` assumption in design.md, adjusting the hook if not
- [x] 8.2 Verify session-expiry/401 on `staff-dashboard`, `staff-audit-trail`, and `staff-visitor-registration` redirect to `/staff/login`, and that admin-only pages still redirect to `/admin/login`
- [x] 8.3 Type-check and lint the changed files
