## 1. Assets

- [x] 1.1 Get the Visimio logos from the backend: run `VMSS_API/scripts/build_brand_assets.py --web-out <this repo>` (or ask the backend owner). The script now emits PNGs (1x and @2x): `logo-visimio{,-on-dark,-mark}{,@2x}.png`, plus `public/favicon.png`, `favicon-32.png`, `apple-touch-icon.png` (user chose PNG over SVG).
- [x] 1.2 `git rm` the three `src/assets/brand/logo-guestify*.svg` files and `public/favicon.svg`, and drop the SVG icon link from `index.html`.

## 2. Brand source and literals

- [x] 2.1 `src/presentation/brand.ts`: import the six `logo-visimio*.png` files (1x/2x), add `src2x`/`darkSrc2x` to `BRAND_LOGOS`, set `BRAND_NAME = 'Visimio'`, and fix the comments ("G" pin mark → Visimio mark).
- [x] 2.2 `index.html`: `<title>Visimio</title>` and remove the `favicon.svg` link. Leave other uncommitted local edits untouched and stage with `git add -p`.
- [x] 2.3 `public/firebase-messaging-sw.js`: fallback title `'Visimio'`.
- [x] 2.4 `e2e/test_toasts.py`: push payload title `'Visimio'`.
- [x] 2.5 `e2e/test_theme_mode.py`: update `ON_DARK_LOGO` and the `img[src*=...]` locator to `logo-visimio`.
- [x] 2.6 Restore `srcSet` (1x/2x) in `BrandLogo.tsx`; check `<BrandLogo>`, `PortalHeader`, `SidebarHeader` and any component comments for hard-coded "Guestify" or "G" mark wording.

## 3. Guard

- [x] 3.1 `scripts/check-brand.mjs`: pattern `/VisitorPass|Guestify/i`; update header comment and error message.
- [ ] 3.2 `npm run lint` passes (brand guard passes; `check-theme-colors` fails on the unrelated `BadgeCardPrint.tsx:50` `bg-white`).

## 4. Specs and change housekeeping

- [x] 4.1 Delete `openspec/changes/rebrand-to-guestify/` (superseded).
- [x] 4.2 Replace Guestify → Visimio in the in-flight `modernize-visitor-flow-pages` and `modernize-visitor-landing-page` changes (proposal, design, tasks, specs), adjusting "G pin"/"Gu"+"estify" descriptions.
- [x] 4.3 Leave `openspec/changes/archive/**` as is (history).

## 5. Sweep

- [x] 5.1 `grep -rniE guestify . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=archive` returns nothing. Also check `.env*`, `package.json`, README/docs and CI config.
- [x] 5.2 `grep -rniE "visitorpass|guestify" src public index.html e2e` returns nothing.

## 6. Verify

- [x] 6.1 `npm run build` and type-check pass.
- [ ] 6.2 In the browser, check each logo slot at 375, 768 and 1440px, light and dark theme: visitor landing, mobile app bar, admin/staff/reception sidebars (expanded and collapsed), staff and SSO login.
- [ ] 6.3 Tab title reads "Visimio" and the favicon/touch icon are the Visimio mark (private window); every copyright line reads "© {year} Visimio. All rights reserved."
- [ ] 6.4 Run `npm run e2e` on its own.

## 7. Coordination (outside this repo)

- [ ] 7.1 Mobile app: same rename of UI copy, app/store names, deep-link and share text, client-built email/SMS copy, logos and icons; grep its repo for "guestify".
- [ ] 7.2 Agree a joint release with backend and mobile to avoid mixed names.
