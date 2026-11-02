## 1. Shared building blocks

- [x] 1.1 Add an optional `trailing?: ReactNode` adornment to `src/presentation/components/ui/TextField.tsx` (design D5). When set:
  - wrap the input in a `relative` div;
  - add right padding to the input;
  - position the adornment at the right edge.

  Existing callers must render unchanged.
- [x] 1.2 Add a `useMinWidth(px)` media-query hook (or reuse an existing one if `src/presentation/hooks/` already has it), with a `matchMedia` change listener and an SSR-safe default of `false`. *Done by reusing the existing `useIsDesktop()` from `use-media-query.ts`.*
- [x] 1.3 Create `src/presentation/components/auth/AuthSplitLayout.tsx` with props `portalLabel` and `children` (design D1/D2):
  - root `flex h-dvh overflow-hidden`, stacking as a column below `lg`;
  - a `lg`+ brand panel with navy gradient, cyan glow, and `HeroImage` rendered only when `useMinWidth(1024)` is true;
  - a `lg:hidden` navy top strip with the on-dark logo and the portal tag;
  - a scrollable form panel that centres `children` and pins the help line (`SUPPORT_EMAIL`) and the `footerLinks` row to the bottom.
- [x] 1.4 Build the brand panel content (design D3):
  - on-dark `BrandLogo`;
  - the portal tag;
  - headline and tagline;
  - three highlights with inline SVG icons (pre-registration, QR check-in, live who's-inside);
  - `copyrightLine()` pinned to the bottom.

  No system-status indicator.
- [x] 1.5 Add the form-block entrance animation (design D6): reuse `motion-fade-in` with `--motion-slow`, `--ease-motion-out` and a small upward translate. Confirm the global reduced-motion rule makes it instant.

## 2. Admin login page (`/admin/login`)

- [x] 2.1 Rewrite `staff-login/staff-login.tsx` to render `useStaffLoginPage()` + `<AuthSplitLayout portalLabel="Admin Portal">` + `LoginFormCard`. The hook stays untouched.
- [x] 2.2 Restyle `LoginFormCard` (design D4):
  - drop the card box;
  - "Welcome back" heading with description;
  - taller inputs;
  - primary "Sign In" button with hover lift;
  - outlined "Sign in with SSO" button;
  - keep the divider and the security note.
- [x] 2.3 Add the password show/hide toggle: local state, `type="button"`, `aria-label` "Show password"/"Hide password", `aria-pressed`, starting hidden. Set `autoComplete="username"` on email and `"current-password"` on password.
- [x] 2.4 Render `errorMessage` as a danger-tinted alert with an icon and `role="alert"`.
- [x] 2.5 Delete `StaffGatewayHeader.tsx` and `StaffLoginFooter.tsx`, and remove their imports.

## 3. Staff SSO login page (`/staff/login`)

- [x] 3.1 Rewrite `staff-sso-login/staff-sso-login.tsx` to render `useStaffSsoLoginPage()` + `<AuthSplitLayout portalLabel="Staff Portal">` + `SsoSignInCard`. The hook stays untouched.
- [x] 3.2 Restyle `SsoSignInCard` to match:
  - "Welcome back" heading with the "Sign in with your organization credentials" description;
  - a single primary "Sign in with SSO" button with the existing pending labels;
  - the security note;
  - the error as a `role="alert"` alert box.
- [x] 3.3 Delete `StaffPortalHeader.tsx` and `StaffSsoLoginFooter.tsx`, and remove their imports.

## 4. Verification

- [x] 4.1 `npm run lint`: oxlint, `check-brand`, `check-grid-spans`, `check-theme-colors`. The new `components/auth/` file must pass without a `theme-fixed` opt-out.
- [x] 4.2 `npm run build:check` (type check + public-page bundle budget).
- [x] 4.3 `npm test` (unit tests; no unit test covers these pages, but `brand.test.ts` and `theme-tokens.test.ts` must stay green).
- [x] 4.4 Manually check both routes at 1920×870, 1024×700, 1280×560, 800×500 and 360×640 (dev server or `npm run screenshots`):
  - at ≥1024×700, no page scroll, with the footer links visible;
  - on short viewports, only the form panel scrolls;
  - below 1024px wide, the top strip replaces the brand panel;
  - at 360px, nothing is clipped.

  Repeat with an empty-submit validation error and a failed sign-in shown.
- [x] 4.5 Check that keyboard tab order runs email → password → show/hide toggle → Sign In → SSO → help link → footer links, and that the focus rings are visible.
- [x] 4.6 Run only the targeted e2e modules, on their own and never alongside API pytest: `test_auth_and_dashboards.py`, `test_toasts.py`, `test_theme_mode.py`. This is not the full e2e suite. *28/29 passed in the combined run. The one failure was the sign-out URL assertion, which passed on its own both with this change and at HEAD, so it's a timing flake. `get_by_label("Password")` substring-matches the new "Show password" toggle, so the two password `fill()` calls now use `get_by_role("textbox", name="Password")`.*
- [x] 4.7 Confirm `rebrand-to-guestify` is archived before archiving this change (design: Risks). *Resolved another way: this change was synced first, and `rebrand-to-guestify`'s superseded `staff-login` delta was removed, so the two can archive in any order.*
