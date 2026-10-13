## 1. Layout

- [x] 1.1 In `visitor-portal-landing.tsx`, change the page wrapper to `flex min-h-dvh flex-col` and make the hero region (background image + overlay + `PortalHero` + card row) a `flex-1` column that centres its content vertically, with `PortalFooter` after it
- [x] 1.2 Replace the card row's `lg:pb-[100px]` with modest bottom padding (about `lg:pb-10`)
- [x] 1.3 In `PortalHero.tsx`, reduce `md:pt-20 md:pb-16` to modest symmetric padding (about `pt-10 pb-8` at `md`+), leaving mobile spacing visually unchanged
- [x] 1.4 If the 1280×800 check (2.2) still overflows, trim `ActionCard` at `lg` only (`lg:p-6`, `lg:gap-5`) and/or tighten hero spacing further; optionally add a `[@media(min-height:900px)]` variant for more spacing on tall screens — not needed: page measured 767px tall at lg, fits 800px without trimming

## 2. Verification

- [x] 2.1 Browser check at 1920×~866 (the user's reported viewport): no vertical scrollbar; header, hero, both cards and footer visible
- [x] 2.2 Browser check at 1280×800 and 1024×800: no vertical scrollbar
- [x] 2.3 Browser check at 1920×1200: hero background reaches the footer with no blank band; content vertically centred
- [x] 2.4 Browser check at 1366×650 and 360px wide: page scrolls normally and nothing is clipped; cards stack on phone
- [x] 2.5 Confirm `/visitor/request` and `/visitor/track` look unchanged (shared header/footer untouched)
- [x] 2.6 Run `npm run lint` and `npm run build` (type check) clean
