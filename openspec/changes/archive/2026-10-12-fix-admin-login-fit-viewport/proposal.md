## Why

On a typical laptop viewport (about 1920×870 visible), the `/admin/login` screen is taller than the window. Users have to scroll to reach the bottom of the sign-in card (SSO button, "Secured by corporate authentication"), the "Need help?" line, and the footer. A sign-in gateway should fit on one screen. The overflow comes from the layout, not the content: `main` carries `md:py-[120px]` (240px of vertical padding), and the card uses `md:p-12` and `md:gap-8` at every desktop height. Together with the header and footer, the page grows to about 1,100px.

## What Changes

- The `/admin/login` page shell is pinned to the viewport height (`h-dvh`). The header stays at the top, the footer stays at the bottom, and the sign-in card plus the "Need help?" line are centered in the space between them.
- The fixed `md:py-[120px]` vertical padding on `main` is replaced with small padding, so free space is distributed by flex centering instead of reserved up front.
- The sign-in card's vertical padding and section gaps get smaller on short viewports (height-based breakpoints), so the full card fits down to roughly 700px of viewport height without scrolling.
- If the viewport is shorter than the content can compress to (for example a landscape phone, or heavy browser zoom), only the middle region scrolls. The page never clips or hides the form, and the header and footer stay in place.
- The hero background image and overlay continue to cover the full viewport and do not stretch the page.
- No change to the form's fields, validation, submit behaviour, SSO action, copy, or branding.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `staff-login`: the "Staff login screen is reachable at a dedicated route" requirement gains a layout clause. On desktop and laptop viewports, the header, the full sign-in card, the help line, and the footer are all visible without page scrolling. On shorter viewports, only the content region scrolls.

## Impact

- **Code**: `src/presentation/pages/staff-login/staff-login.tsx` (page shell / `main` layout) and `src/presentation/pages/staff-login/Components/LoginFormCard.tsx` (height-responsive spacing). `StaffGatewayHeader` and `StaffLoginFooter` become `shrink-0` and get tighter vertical padding on short viewports. `src/styles/index.css` gains two height-based `@custom-variant`s.
- **Not in scope**: `/staff/login` (`staff-sso-login.tsx`) uses the same shell with the same `md:py-[120px]` padding and probably has the same issue, but it was not reported and has a much shorter card. It can be fixed in a follow-up using the same pattern.
- **APIs / backend**: none.
- **Dependencies**: none. Uses existing Tailwind utilities (Tailwind v4 arbitrary `[@media(max-height:…)]` variants, or a `@custom-variant` declared in CSS).
