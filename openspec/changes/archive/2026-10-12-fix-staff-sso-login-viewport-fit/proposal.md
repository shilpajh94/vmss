## Why

The staff Enterprise Sign In screen at `/staff/login` is taller than a typical laptop viewport (for example 1920×870), so the whole page scrolls. The header scrolls off the top, and the footer is only visible after scrolling down. The screen should fit within one viewport. `/admin/login` already received this fix in `fix-admin-login-fit-viewport` (archived 2026-10-12). That change deferred `/staff/login` to a separate change, and this is that change.

## What Changes

- Pin the `/staff/login` page shell to the viewport height. The header stays at the top edge, the footer stays at the bottom edge, and the lobby background covers exactly the viewport.
- Remove the fixed 240px of vertical padding (`md:py-[120px]`) around the card. Center the card and the "Need help?" line in the space left between header and footer.
- Use the existing `short` / `xshort` height variants (`src/styles/index.css`) to tighten the card, header, and footer spacing on shorter screens, matching `/admin/login`.
- When the viewport is too short for the content (a phone, a small landscape window), only the content region between header and footer scrolls. No part of the card is clipped.
- No change to copy, the card's design at tall viewports, or SSO sign-in behaviour.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-sso-login`: the "Staff SSO login screen is reachable at a dedicated route" requirement gains viewport-fit behaviour. With no page scrolling at ≥1024×700, everything is visible at once, and short viewports scroll only the content region. This mirrors the `staff-login` (`/admin/login`) requirement.

## Impact

- Code (VMMS_WEB only): `src/presentation/pages/staff-sso-login/staff-sso-login.tsx` and `Components/SsoSignInCard.tsx`, `StaffPortalHeader.tsx`, `StaffSsoLoginFooter.tsx`. Changes are layout and Tailwind classes only.
- No API, routing, state, or dependency changes. VMSS_API is unaffected.
