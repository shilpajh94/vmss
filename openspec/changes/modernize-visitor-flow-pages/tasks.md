## 1. Prerequisites and shared shell

- [ ] 1.1 Confirm `modernize-visitor-landing-page` is archived. If it isn't, finish and archive it first (design D8).
- [x] 1.2 Take "before" screenshots at 1440×900 and 375×667 of every screen in the proposal's table:
  - OTP request and OTP verify;
  - history (seed a returning visitor);
  - a wizard step, the review step and the confirmation;
  - track lookup, track result and track no-result;
  - not-found and route error;
  - `/`, `/admin/login` and `/staff/login`, for the no-regression check. *27 shots per run via a scratch Playwright script (OTP read from Mailpit, a real submission for review/confirmation/track result, history for that same email, route error via an aborted layout chunk).*
- [x] 1.3 Extend `SplitScreenLayout` with `back`, `panel`, `panelClassName` and `align`, plus a way to hide the portal tag row (design D1). The defaults must keep `/`, `/admin/login` and `/staff/login` byte-identical in screenshots. *Added `back`, `panel`, `panelClassName`, `align` and `showPortalTag`; the footer also gets `max-lg:py-4` so a tall phone stays within the 16px padding rule.*
- [x] 1.4 Add `components/layout/visitor-brand.tsx` with `VISITOR_BRAND` and `visitorFooterLinks()` (design D2), and switch `visitor-portal-landing.tsx` to it.

## 2. OTP and history screens

- [x] 2.1 Rewrite `OtpScreenLayout` as the `SplitScreenLayout` wrapper (design D3): visitor brand, `back` as an `onClick` handler, and an `align` pass-through. Remove the in-photo title and the white back button.
- [x] 2.2 Restyle `OtpRequestScreen` and `OtpVerifyScreen`:
  - no card;
  - an `h1` heading;
  - the cyan primary button;
  - `AuthErrorAlert` for request and verify errors;
  - every label and button name kept. *The heading uses `AuthFormHeading` with its description now optional, so no new copy was added.*
- [x] 2.3 Restyle `ReturnVisitHistoryScreen` (an `h1`, no outer card, "Start a new request" as the primary button) and the history-lookup skeleton. Pass `align="start"` for the history screen.
- [x] 2.4 Remove `PortalHeader` and `PortalFooter` from the OTP, lookup and history branches of `visitor-request.tsx`.

## 3. Registration wizard

- [x] 3.1 Give `StepSidebar` an on-dark variant (design D4):
  - sidebar-token labels;
  - a cyan marker and connector fill;
  - dimmed upcoming steps;
  - completed steps still selectable. *`StepSidebar` is only used by the wizard, so it was restyled in place instead of gaining a variant; `StepMarker` (shared with the staff stepper) got an opt-in `onDark`.*
- [x] 3.2 Render the wizard branch on `SplitScreenLayout`:
  - `panel` = the on-dark `StepSidebar`, `panelClassName="w-[340px]"`, `align="start"`;
  - `back` → `navigate('/')`;
  - a 760px content column with no portal tag row.

  Remove `PortalHeader` and `PortalFooter`.
- [x] 3.3 Drop the form card border. Keep the action bar `sticky bottom-0` inside the scroll panel at every width, with "Next" in cyan and "← Back" outlined. Drop the `StepProgressHeader` card border.
- [x] 3.4 Check that Back from a step with typed data shows the existing unsaved-changes confirmation. Check that the review step and the post-submit confirmation (tracking ID, "go home") render correctly in the new panel. *Checked in a browser at 1440×700 and 375×667: Back with typed data shows the confirmation and stays on the page.*

## 4. Track page

- [x] 4.1 Rewrite `visitor-track.tsx` on `SplitScreenLayout` (design D5): visitor brand, `back={{ to: '/' }}`, a 520px column, and `align` switching to `start` once a lookup has run. Remove the photo backdrop, the in-photo title, `PortalHeader` and `PortalFooter`.
- [x] 4.2 Restyle `TrackingLookupCard`: no card, an `h1`, and the cyan "Track Request" button with its existing placeholder and label. Soften `StatusPanel`'s shadow and keep its border. Render the no-result state as `AuthErrorAlert` with "No Result".

## 5. Not-found and error pages

- [x] 5.1 Rewrite `not-found.tsx` on `SplitScreenLayout` (design D6), keeping the session-aware home link and its labels.
- [x] 5.2 Rewrite `route-error.tsx` on `SplitScreenLayout` with no `back` and no router-dependent props. Keep `useForceLightTheme()`, `role="alert"` and the "Reload" button.

## 6. Cleanup, specs housekeeping and tests

- [x] 6.1 Delete `components/PortalHeader.tsx` and `components/PortalFooter.tsx`, and confirm nothing imports them (design D7).
- [x] 6.2 Remove the "Logo Variant Matches Its Background" requirement from `openspec/changes/rebrand-to-guestify/specs/brand-identity/spec.md`, add a note to that change's proposal, and confirm `openspec validate rebrand-to-guestify --strict` passes (design D8).
- [x] 6.3 Update `e2e/test_theme_mode.py::test_error_page_renders_light_in_dark_mode`: light theme, and exactly one visible logo whose `src` is the on-dark lockup.
- [x] 6.4 Update `e2e/test_responsive_matrix.py::test_public_footer_is_compact` to measure the split-screen footer on `/visitor/track`:
  - at most 88px tall at 1440px;
  - at most 16px vertical padding at 360px;
  - no horizontal overflow.

## 7. Verification

- [x] 7.1 `npm run lint`: `check-theme-colors` must pass for `pages/not-found` and `components/layout` without opt-outs. Also run `npm run build:check` (budget) and `npm test`. *Lint clean apart from two pre-existing warnings in `use-visitor-request-wizard.ts`; landing initial JS 186.59 kB / 350 kB; 75/75 unit tests.*
- [x] 7.2 Compare the "after" screenshots for `/`, `/admin/login` and `/staff/login` with 1.2: byte-identical. *All six (`/`, `/admin/login`, `/staff/login` at both sizes) are byte-identical.*
- [x] 7.3 Check each screen from 1.2 at 1440×900, 1024×700 and 375×667:
  - no page scroll;
  - only the content panel scrolls;
  - the strip shows below 1024px;
  - no lobby photo request at 375px or on the wizard;
  - Back works on the OTP, history, wizard and track screens;
  - the sticky wizard actions stay visible on a long step. *41/41 scripted checks passed. Found and fixed a hover flicker: the cyan button's 1px hover lift moved it off a pointer resting on its bottom edge, so it never settled (a strip under the button now covers that row).*
- [x] 7.4 Run only the targeted e2e modules, on their own and never alongside API pytest:
  - `test_visitor_self_service.py`;
  - `test_invitation_lifecycle.py`;
  - `test_theme_mode.py`;
  - `test_responsive_matrix.py`;
  - `test_auth_and_dashboards.py`, for the shared shell.

  This is not the full suite.

  *Narrowed at the user's request to the tests covering the changed pages: `test_visitor_self_service.py`, `test_theme_mode.py::test_error_page_renders_light_in_dark_mode`, `test_responsive_matrix.py::test_public_footer_is_compact`, `test_auth_and_dashboards.py::test_admin_signs_in_with_password_and_signs_out`, and the two `test_toasts.py` tests that use the sign-in page: 6 passed. A sweep of the six public routes at 320–1920px wide found no overflow and no page scroll (48/48). An earlier broad run had two `test_paged_list_pagination_stays_visible` failures on admin list pages, which this change doesn't touch; not investigated.*
