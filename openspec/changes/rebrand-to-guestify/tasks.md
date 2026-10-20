## 1. Assets

- [x] 1.1 Confirm that the user has approved the SVG master (API task 2.7) and that the paired `VMSS_API` change has run `build_brand_assets.py --web-out ../VMMS_WEB`. These files must exist: `src/assets/brand/logo-guestify{,-on-dark,-mark}.svg`, `public/favicon.svg`, and the re-rendered `public/favicon.png`, `favicon-32.png` and `apple-touch-icon.png`.
- [x] 1.2 Delete the six `src/assets/brand/logo-visimio*.png` files.

## 2. Brand source and literals

- [x] 2.1 `src/presentation/brand.ts`: replace the six PNG imports with three `logo-guestify*.svg` imports, make each `BRAND_LOGOS` entry `{ src }` only, set `BRAND_NAME = 'Guestify'`, and change the "V" mark comment to the "G" pin mark.
- [x] 2.2 `components/BrandLogo.tsx`: drop `srcSet`/`src2x`, keeping the sizing classes (design Decision 1).
- [x] 2.3 `components/PortalHeader.tsx` and `components/sidebar/SidebarHeader.tsx`: set `aria-label` to `` `${BRAND_NAME} home` `` (design Decision 2).
- [x] 2.4 `components/BrandLogo.tsx`: change the comment's "Visimio" reference to `BRAND_NAME`/Guestify.
- [x] 2.5 `index.html`: change the `<title>` line to `Guestify`, and add `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />` before the PNG icon links. Leave the other uncommitted local edits in the file untouched, and stage with `git add -p`.
- [x] 2.6 `public/firebase-messaging-sw.js`: make the fallback notification title `'Guestify'`.
- [x] 2.7 `e2e/test_toasts.py`: set the push payload title to `'Guestify'`.

## 3. Guard

- [x] 3.1 `scripts/check-brand.mjs`: change the pattern to `/VisitorPass|Visimio/i` and update its header comment and error message (Decision 3).
- [x] 3.2 Run `npm run lint`. It must pass, which proves no "Visimio" remains under `src`, `public` or `index.html`.

## 4. Verify

- [x] 4.1 `npm run build` succeeds, and the type-check is clean.
- [x] 4.2 In the browser (DDEV dev server), check every logo slot at 375, 768 and 1440px. Check for no clipping, no navy box behind the light lockup, crisp rendering at 2× density and at 200% browser zoom, and the collapse control still visible:
  - visitor landing header and footer;
  - mobile app bar;
  - admin, staff and reception sidebars, expanded and collapsed;
  - staff login header and footer;
  - SSO login header and footer.

  Adjust a slot's height class only where one fails (Decision 4).
- [x] 4.3 Check that the tab title reads "Guestify" and the favicon shows the "G" mark (use a private window to bypass the favicon cache), and that every copyright line reads "© {year} Guestify. All rights reserved."
- [ ] 4.4 Run the e2e suite (`npm run e2e`) on its own, never alongside pytest.

## 5. Support contact and brand sweep

- [x] 5.1 Add `VITE_SUPPORT_EMAIL=` to `.env.example`, with a comment that it's optional and the footer hides the line when unset. Do not stage `.env`.
- [x] 5.2 Add `SUPPORT_EMAIL` to `src/presentation/brand.ts`, read once from `import.meta.env.VITE_SUPPORT_EMAIL`, trimmed, with an empty value treated as unset. `PortalFooter.tsx` renders the `mailto:` link only when it is set.
- [x] 5.3 `scripts/check-brand.mjs`: make the pattern `/VisitorPass|Visimio/i` again (case-insensitive, now that the footer address is gone). `npm run lint` must pass.
- [x] 5.4 Final sweep: running `grep -rniE "visimio|visitorpass" src public index.html e2e` must return nothing.

## 6. Follow-up

- [ ] 6.1 After archive, retitle the main-spec scenario "Sidebar shows the Visimio logo" to "Sidebar shows the Guestify logo" in `openspec/specs/brand-identity/spec.md`. The delta had to keep the old scenario name to match.
- [x] 6.2 In the still-open change `role-based-invitation-workflow`, change task 187's reference to the old "VisitorPass" wordmark header to "the brand logo header". It's wording only, so that change's plan doesn't send anyone looking for a header that no longer exists.
