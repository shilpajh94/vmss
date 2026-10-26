## Why

The admin (`/admin/login`) and staff (`/staff/login`) sign-in pages are the first thing every employee sees. Today they show a white card on a darkened lobby photo, between a solid navy header bar and a footer. The look is dated and generic: there is no product story and no password visibility toggle. The header also shows a hard-coded "All Systems Operational" badge that nothing actually checks. The rest of the portal has since been modernised (new dropdowns, motion, Guestify rebrand). The sign-in pages should now match that standard and present Guestify as a polished product.

## What Changes

- Replace the header bar, photo backdrop and centred card on both login pages with a **split-screen layout**:
  - **Brand panel** (left, on wide screens): the lobby photo under a navy-to-cyan gradient, the Guestify on-dark logo, a portal tag ("Admin Portal" / "Staff Portal"), a headline and tagline, three product highlights, and the copyright line.
  - **Form panel** (right): a clean surface with no card box. It holds a "Welcome back" heading, the existing sign-in controls, the security note, the help link and the footer links.
- Below the desktop breakpoint, the brand panel collapses to a slim navy strip with the logo and portal tag above a full-width form.
- Build both pages on one shared `AuthSplitLayout`. The two near-identical header components and the two footer components are removed.
- Admin form refinements:
  - a show/hide toggle on the password field;
  - correct `autocomplete` hints (`username` / `current-password`);
  - the inline error shown as an icon alert (`role="alert"`) instead of plain red text.
- SSO card refinements: the same heading and alert treatment, with the SSO action kept as the single primary button.
- A short entrance animation on the form panel, drawn from the shared motion scale and switched off under reduced motion.
- **Removed:** the static "All Systems Operational" indicator and the "ADMIN GATEWAY" / "STAFF GATEWAY" header badges. The portal tag on the brand panel or strip takes over the badges' job.
- Unchanged:
  - routes;
  - sign-in behaviour: password login, SSO start and completion, error toasts, role-based redirect, already-signed-in redirect;
  - the always-light theme on public pages;
  - the accessible names that tests rely on ("Email", "Password", "Sign In", "Sign in with SSO").

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `staff-login`:
  - the route requirement's layout description changes from header + centred card + footer to the split-screen layout;
  - the viewport-fit rules are restated for the new layout;
  - the "visually distinct" requirement is rewritten for the brand panel (no Admin Gateway header or status indicator);
  - a new requirement covers the password visibility toggle.
- `staff-sso-login`: the route requirement's layout description and viewport-fit rules change the same way. The card content changes from "Enterprise Sign In" to the new heading treatment.

## Impact

- **Code (VMMS_WEB only):**
  - `src/presentation/pages/staff-login/` and `src/presentation/pages/staff-sso-login/`: page shells, `LoginFormCard`, `SsoSignInCard`. `StaffGatewayHeader`, `StaffPortalHeader`, `StaffLoginFooter` and `StaffSsoLoginFooter` are removed.
  - New `src/presentation/components/auth/AuthSplitLayout.tsx` (with the brand panel).
  - `TextField` gains an optional trailing-adornment slot for the password toggle, used only here.
- **No API changes:**
  - no new dependencies;
  - the existing `HeroImage` assets, the `BrandLogo` on-dark variant and the theme tokens are reused;
  - the public-page download budget (`check-bundle-budget.mjs`) must still pass.
- **Tests:**
  - e2e `test_auth_and_dashboards.py`, `test_toasts.py` and `test_theme_mode.py` must stay green; they use labels and button names only;
  - `scripts/screenshot-pages.py` already captures both routes for visual review.
- **Specs:** `brand-identity` needs no change. The on-dark logo still sits on a navy surface, and the copyright line moves to the brand panel or form-panel footer.
