## 1. Page shell

- [x] 1.1 In `src/presentation/pages/staff-sso-login/staff-sso-login.tsx`, change the root from `min-h-screen` to `h-dvh … overflow-hidden`
- [x] 1.2 Turn `main` into the scroll region (`relative min-h-0 flex-1 overflow-y-auto`). Move the card and the "Need help?" line into an inner `flex min-h-full flex-col items-center justify-center` wrapper, using the same gap/padding classes as `staff-login.tsx`, and drop `md:py-[120px]`

## 2. Chrome and card spacing

- [x] 2.1 `StaffPortalHeader.tsx`: add `shrink-0` and `xshort:py-3`
- [x] 2.2 `StaffSsoLoginFooter.tsx`: add `shrink-0` and `xshort:py-3`
- [x] 2.3 `SsoSignInCard.tsx`: apply the `short`/`xshort` gap and padding tiers from `LoginFormCard.tsx`, on the card root, the title block (`xshort:gap-2`), and the button/error block (`xshort:gap-3`)

## 3. Verification

- [x] 3.1 `npm run build` (type-check + build) and lint pass
- [x] 3.2 In devtools or headless Chromium, check `/staff/login` at 1920×870, 1366×768, 1280×720, and about 1533×697 (125% scaling): there is no page scrollbar, and the header, full card, "Need help?" line, and footer are visible
- [x] 3.3 Force a failed sign-in (for example `/staff/login?code=invalid`) at 1920×870: the inline error and the toast are visible, and there is no page scroll
- [x] 3.4 At 800×500 and 360×640, the header and footer stay fixed, only the content region scrolls, and the whole card (including "Sign in with SSO") is reachable
- [x] 3.5 Compare side by side with `/admin/login` at the same viewport: the header, footer, and card spacing match
