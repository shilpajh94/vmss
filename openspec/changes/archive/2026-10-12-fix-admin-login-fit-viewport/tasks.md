## 1. Page shell

- [x] 1.1 In `src/presentation/pages/staff-login/staff-login.tsx`, change the root from `min-h-screen` to `h-dvh overflow-hidden` (Tailwind v4 already targets browsers with `dvh` support, so no `h-screen` fallback) (keep `relative flex w-full flex-col`)
- [x] 1.2 Make `StaffGatewayHeader` and `StaffLoginFooter` non-shrinking (`shrink-0` on their root elements)
- [x] 1.3 Change `main` to `relative flex-1 min-h-0 overflow-y-auto`, and remove `justify-center`, `items-center`, gap, and the `py-12 md:py-[120px]` padding from it
- [x] 1.4 Inside `main`, wrap the card and "Need help?" line in one `div` with `flex min-h-full flex-col items-center justify-center gap-4 md:gap-6 px-4 md:px-12 py-6 md:py-8` (safe centering, design §2)

## 2. Card spacing

- [x] 2.1 Declare the `short` (≤900px) and `xshort` (≤800px) height variants in `src/styles/index.css`. In `LoginFormCard.tsx`, keep `md:p-12 md:gap-8` and add the `short`/`xshort` spacing overrides. Tighten the wrapper, header and footer under `xshort` (design §3)

## 3. Verify

- [x] 3.1 In devtools at 1920×870, 1366×768, and 1280×720: confirm the header, the full card down to "Secured by corporate authentication", "Need help?", and the footer are visible with no page scrollbar. Adjust the breakpoints or the gaps if not
- [x] 3.2 At 1920×870, submit the empty form and confirm the validation messages show and the footer stays visible
- [x] 3.3 At 800×500 and 360×640: confirm the header and footer stay put, the card region scrolls, and the top of the card (the "Admin Portal" badge) is reachable (not clipped by centering)
- [x] 3.4 Trigger a failed login and confirm the error toast still appears above the page
- [x] 3.5 Confirm the background image covers the full viewport with no gap below the footer
- [x] 3.6 Run `npm run lint` and `npm run build` and confirm both are clean
