## Why

The product is being renamed from **VisitorPass** to **Visimio**, with a
new logo (`assets/visimio-logo-source.png`: a cyan "V" mark and a dark
"Visimio" wordmark). The portal still shows the old name in every
sidebar, header, footer and copyright line. It shows a placeholder "V"
tile and the old gradient mark, the browser tab says "VMSS", and the
favicon is still Vite's default purple bolt. The API's emails are being
rebranded in parallel (`VMSS_API` change
`refine-email-templates-and-visimio-brand`), and the portal has to match.

## What Changes

- **New brand assets** generated from the supplied logo:
  - `logo-visimio.png`: full lockup, dark wordmark, for light surfaces;
  - `logo-visimio-on-dark.png`: white wordmark, for the navy sidebars and
    staff headers;
  - `logo-visimio-mark.png`: the "V" mark alone, for compact spots;
  - `favicon.png` + `apple-touch-icon.png`: the mark on a transparent or
    white square.

  All are produced at 1× and 2× for crisp rendering. The old
  `logo.svg`/`logo-mark.svg` and the Vite `favicon.svg` are removed.
- **Replaced everywhere:**
  - admin, staff and reception sidebars, and the mobile nav bar: on-dark
    lockup;
  - visitor portal header and footer: light lockup, replacing the "V" tile
    plus text;
  - staff login and SSO login headers: on-dark lockup;
  - both login footers and the portal footer: "© {current year} Visimio.
    All rights reserved.";
  - `index.html`: `<title>Visimio</title>`, favicon, apple-touch-icon,
    and `theme-color`;
  - push-notification fallback title in `firebase-messaging-sw.js`:
    "Visimio".
- **One brand source of truth:** a `brand.ts` module exporting
  `BRAND_NAME = 'Visimio'` and the asset imports. A `<BrandLogo
  variant="light|on-dark|mark" />` component uses them, so no component
  hard-codes the name or the image path again.
- The alt text of every logo image is "Visimio". Where the logo is the
  home link, the link has the accessible name "Visimio home".

Out of scope: internal identifiers (package name `vmss`, env var names,
repo names) and tenant-uploaded company logos, which aren't shown in the
portal today.

## Capabilities

### New Capabilities
- `brand-identity`: The product name, logo variants, favicon, document
  title and copyright line the portal shows, and the rule that they come
  from one brand module.

### Modified Capabilities
- `staff-login`: The dark header's brand mark is the Visimio on-dark logo
  instead of the "VisitorPass" text mark.
- `visitor-portal-landing`: The product name shown in the header and
  footer is "Visimio", via the logo.

## Impact

- `src/assets/brand/`: new PNG assets, generated once from the source
  PNG by the API repo's Pillow script
  (`VMSS_API/scripts/build_brand_assets.py --web-out`) and committed. There
  is no new web dependency. The old SVG logos and `public/favicon.svg` are
  removed.
- `src/presentation/brand.ts` and `components/BrandLogo.tsx` are new.
- Edited: `AdminSidebar`, `DashboardSidebar`, `ReceptionSidebar`,
  `AppShell` (mobile bar), `PortalHeader`, `PortalFooter`,
  `StaffGatewayHeader`, `StaffPortalHeader`, `StaffLoginFooter`,
  `StaffSsoLoginFooter`, `index.html`, and `public/firebase-messaging-sw.js`.
- No API or routing change. Bundle size grows by about 30 KB of PNGs.
