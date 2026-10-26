## Why

The sign-in pages and the visitor landing page now use the modern split-screen design (`modernize-login-pages`, `modernize-visitor-landing-page`). Every other public screen still uses the old look: a white header bar, a darkened lobby photo, a white card with a navy button, and a white footer bar. As a visitor goes from the landing page into requesting or tracking a visit, the design switches back to the old style halfway through. All public screens should look like one product.

## What Changes

Move every remaining public screen onto the shared split-screen layout:

| Screen | Route | New layout |
|---|---|---|
| OTP request ("Request a visit") | `/visitor/request` | Split screen: visitor brand panel + form panel |
| OTP verify ("Verification code") | `/visitor/request` | Split screen |
| Looking up your visits (skeleton) | `/visitor/request` | Split screen |
| Return-visit history | `/visitor/request` | Split screen; the history list scrolls in the content panel |
| Registration wizard (every step, review, confirmation) | `/visitor/request` | **Navy step panel**: the left navy panel shows the logo, back link and step list instead of the brand copy; the form is on the right |
| Track lookup, status result, no-result | `/visitor/track` | Split screen; the result appears under the lookup form |
| Page not found | any unknown path | Split screen |
| Something went wrong | router error | Split screen |

- **Shared shell:**
  - one visitor brand copy (headline, tagline, highlights) and one footer link set (Privacy Policy, Terms of Service, configured support contact) are shared by the landing page and every visitor screen;
  - the back action moves into the brand panel or top strip;
  - forms lose their card boxes, like the sign-in forms;
  - primary actions become the cyan button;
  - errors use the shared alert.
- **Wizard:**
  - from 1024px wide, the step list lives in the navy panel, with cyan progress markers and the existing jump-back-to-completed-step behaviour;
  - below 1024px, the navy top strip sits above the existing compact "Step X of N" progress header;
  - Back/Next stay pinned at the bottom of the scrolling form panel.
- **Removed:** the white `PortalHeader` and `PortalFooter` and the in-photo page titles. No page uses them after this change.
- **Unchanged:**
  - routes;
  - OTP, history, wizard, submission and tracking behaviour;
  - the always-light theme;
  - all field labels and button names (with one exception: the request and verify buttons change only in colour).

## Capabilities

### New Capabilities

- `public-page-layout`: defines the shared split-screen shell (brand panel or top strip, content-panel-only scrolling, desktop-only photo, footer links, back action) and lists every public page that must use it.

### Modified Capabilities

- `visitor-otp-verification`: "OTP screens share the portal's visual theme" now requires the shared split-screen layout instead of the shared header and footer.
- `visitor-request-wizard`: "Step navigation adapts to narrow viewports" now places the step list in the navy panel from 1024px wide (today the rail is hidden below `lg`, not 768px as the spec says) and the compact progress header below that.
- `responsive-layout`: "The Public Portal Footer Is Compact" is rewritten for the split-screen footer, now the only public footer. This builds on `modernize-visitor-landing-page`'s version of the requirement.
- `brand-identity`: "Logo Variant Matches Its Background" no longer cites the visitor portal header as a light surface. Public pages now carry the white-wordmark logo on navy, and the phone navigation bar is the remaining light surface. The Guestify wording from `rebrand-to-guestify` is carried over.
- `theme-mode`: the error-page scenario of "Public pages always render in the light theme" changes from "header and footer logos" to the split-screen brand panel or strip.

## Impact

- **Code (VMMS_WEB only):**
  - `components/layout/SplitScreenLayout.tsx` gains a back action, a brand-panel slot (for the wizard's steps), a panel-width option and top-aligned content;
  - `visitor-request/` (page shell, `OtpScreenLayout`, the OTP and history screens, `StepSidebar`, `StepProgressHeader` colours, the wizard action bar);
  - `visitor-track/` (page, `TrackingLookupCard`, `StatusPanel`, no-result box);
  - `not-found/` (both pages);
  - `PortalHeader.tsx` and `PortalFooter.tsx` are deleted.
- **No API changes, no new dependencies.** The landing-page download budget must still pass.
- **Tests:** these e2e tests change:
  - `test_theme_mode.py::test_error_page_renders_light_in_dark_mode` asserts a header and footer with the dark-wordmark logo; it will assert the on-dark logo in the brand panel instead;
  - `test_responsive_matrix.py::test_public_footer_is_compact` measures the old shared footer; it will measure the split-screen footer.

  The visitor e2e flows (`test_visitor_self_service.py`, `test_invitation_lifecycle.py`) must stay green; they select by labels and button names.
- **Order:**
  - archive `modernize-visitor-landing-page` before this change, because this change builds on its layout and footer requirement;
  - this change drops `rebrand-to-guestify`'s superseded "Logo Variant" requirement from that change's `brand-identity` delta.
