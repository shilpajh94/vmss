## 1. Brand assets

- [x] 1.1 Once `VMSS_API/scripts/build_brand_assets.py` exists (API change `refine-email-templates-and-visimio-brand`, task 1.1), run it with `--web-out` to produce the lockup, on-dark lockup and mark at 1×/2× into `src/assets/brand/`, plus `public/favicon.png`, `public/favicon-32.png` and `public/apple-touch-icon.png` (design.md Decision 1).
- [x] 1.2 Review each PNG visually on white and on `#0f172a`: no dark halo on the on-dark variant, and the mark crop is tight. Commit the PNGs, and delete `src/assets/logo.svg`, `src/assets/logo-mark.svg` and `public/favicon.svg`.

## 2. Brand module

- [x] 2.1 Add `src/presentation/brand.ts` (`BRAND_NAME`, `copyrightLine()`, and asset imports).
- [x] 2.2 Add `src/presentation/components/BrandLogo.tsx` with the `light`, `on-dark` and `mark` variants, `srcSet` 2×, and alt `BRAND_NAME` (design.md Decision 2).

## 3. Replace old branding

- [x] 3.1 `AdminSidebar`, `DashboardSidebar`, `ReceptionSidebar`: replace `logoMark` plus "VisitorPass" text with `<BrandLogo variant="on-dark" />`, keeping the home-button behaviour and adding `aria-label="Visimio home"`.
- [x] 3.2 `AppShell` mobile nav bar: `<BrandLogo variant="light" className="h-7" />`.
- [x] 3.3 `PortalHeader` and `PortalFooter`: replace the "V" tile plus text with `<BrandLogo variant="light" />`. The home link gets `aria-label="Visimio home"`. The footer gains `copyrightLine()`.
- [x] 3.4 `StaffGatewayHeader` and `StaffPortalHeader`: `<BrandLogo variant="on-dark" />`. `StaffLoginFooter` and `StaffSsoLoginFooter`: `copyrightLine()`.
- [x] 3.5 `index.html`: `<title>Visimio</title>`, `<link rel="icon" type="image/png" href="/favicon.png">` (plus a 32 px size), `apple-touch-icon`, and `<meta name="theme-color" content="#0f172a">`.
- [x] 3.6 `public/firebase-messaging-sw.js`: fallback notification title "Visimio", with a comment pointing to `brand.ts`.

## 4. Guardrail and verification

- [x] 4.1 Add `scripts/check-brand.mjs`, which fails on any `VisitorPass` in `src/`, `index.html` or `public/`, and chain it into `npm run lint`.
- [x] 4.2 `npm run build` and `npm run lint` are clean.
- [ ] 4.3 Manual check: the landing page, visitor request/track pages, staff and SSO login, and the admin, staff and reception shells, each at 375px and 1440px. The logo is legible and correctly sized, the favicon and tab title show Visimio, and each copyright line shows the current year.
