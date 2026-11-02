## 1. Shared split-screen layout

- [x] 1.1 Take "before" screenshots of `/admin/login` and `/staff/login` at 1920×870 and 360×640 for the no-regression comparison in 4.3.
- [x] 1.2 Move `components/auth/AuthSplitLayout.tsx`'s shell into `components/layout/SplitScreenLayout.tsx` (design D1). Its props are `portalLabel`, `brand` (headline, tagline, highlights), `footerLinks`, an optional `aside`, `contentClassName` and `children`. Keep the following inside it:
  - photo gating with `useIsDesktop`;
  - the mobile strip;
  - the scroll container;
  - copyright placement;
  - the empty-desktop-footer rule;
  - `.auth-form-enter`.
- [x] 1.3 Reduce `AuthSplitLayout` to a wrapper that passes the current sign-in brand copy, the Security/Terms links and the "Need help?" line. The sign-in pages need no edits.

## 2. Landing page

- [x] 2.1 Rewrite `ActionCard` as a single whole-card `<Link>` (design D3):
  - icon tile, title, description, and a call-to-action row with an arrow;
  - primary (cyan) and secondary (outlined) variants;
  - hover lift and a visible focus ring.
- [x] 2.2 Rewrite `visitor-portal-landing.tsx` on `SplitScreenLayout` (design D2/D4):
  - `portalLabel="Visitor Portal"`, visitor brand copy and highlights, and `contentClassName` for the 480px column;
  - a "Welcome" heading and description;
  - the two stacked cards;
  - footer links for Privacy, Terms and, when configured, "Support Contact: {email}".
- [x] 2.3 Delete `Components/PortalHero.tsx`. Confirm that `PortalHeader` and `PortalFooter` are still imported by the request, track, not-found and route-error pages, and are left unchanged.

## 3. Tests and specs housekeeping

- [x] 3.1 Point `e2e/test_responsive_matrix.py::test_public_footer_is_compact` at `/visitor/track` instead of `/`.
- [x] 3.2 Delete `openspec/changes/rebrand-to-guestify/specs/visitor-portal-landing/`, and update that change's proposal line to say this change carries the requirement (design D5). Then confirm `openspec validate rebrand-to-guestify --strict` passes.

## 4. Verification

- [x] 4.1 `npm run lint`: the new `components/layout/` file must pass `check-theme-colors` without an opt-out.
- [x] 4.2 `npm run build:check` (type check + landing-page bundle budget) and `npm test`.
- [x] 4.3 Compare the sign-in "after" screenshots with 1.1: no visible change. *All four screenshots are byte-identical.*
- [x] 4.4 Check `/` manually at 1920×866, 1920×1200, 1024×700, 1366×560 and 360×640:
  - no page scroll at ≥1024×700;
  - only the action panel scrolls on short viewports;
  - the top strip shows below 1024px wide;
  - no lobby photo request at 360px (*only Vite's dev `?import` module stubs; the image itself is fetched on desktop only*);
  - clicking card description text navigates;
  - the cards are reachable by Tab with a visible focus ring.
- [x] 4.5 Run only the targeted e2e modules, on their own: `test_responsive_matrix.py`, `test_visitor_self_service.py` and `test_theme_mode.py` (which loads `/`), plus `test_auth_and_dashboards.py` for the refactored sign-in layout. This is not the full suite.

  *Run together with `modernize-visitor-flow-pages` 7.4, narrowed to the tests covering the changed pages: 6 passed.*
