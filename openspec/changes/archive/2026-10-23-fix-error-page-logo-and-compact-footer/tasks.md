## 1. Error page renders light

- [x] 1.1 `src/presentation/context/theme-mode-context.tsx`: add and export `useForceLightTheme()`, which needs no provider. In a `useLayoutEffect` it sets `pageScope = 'light'` and calls `writeTheme('light')`. Add a one-line comment naming the theme-mode requirement (design D1).
- [x] 1.2 `src/presentation/pages/not-found/route-error.tsx`: call `useForceLightTheme()` at the top of `RouteErrorPage`. Extend the header comment to say why the page forces light itself (it renders outside `PublicLayout` and every provider).

## 2. Theme-following logo

- [x] 2.1 `src/presentation/brand.ts`: add the `'themed'` key to the variant set, so `BrandLogoVariant` includes it. Comment that it means "follows the theme: dark wordmark in light, white wordmark in dark". Keep `light`, `on-dark` and `mark` unchanged (design D2).
- [x] 2.2 `src/presentation/components/BrandLogo.tsx`: for `variant="themed"`, render the `light` image with `dark:hidden` and the `on-dark` image with `hidden dark:block`. Both get the same sizing classes and the same `alt` (empty when `decorative`). Other variants render as before.
- [x] 2.3 `src/presentation/components/AppShell.tsx` (`MobileNavBar`), `PortalHeader.tsx` and `PortalFooter.tsx`: switch `variant="light"` to `variant="themed"`.

## 3. Compact footer

- [x] 3.1 `src/presentation/components/PortalFooter.tsx`:
  - footer padding becomes `px-4 py-4 md:px-12 lg:py-5`;
  - the outer gap becomes `gap-3`;
  - the brand block becomes a one-row layout from `lg` (`lg:flex-row lg:items-center lg:gap-4`), with the `max-w-[400px]` cap removed;
  - drop the tagline's `mt-1`;
  - keep the logo `h-7` and keep the links' `min-h-10 … lg:min-h-0` (design D3).
- [x] 3.2 Check that the landing page still fits 1920×866 and 1280×800 without vertical scroll (visitor-portal-landing "Landing page fits a desktop viewport without scrolling"). The footer only got shorter, so this is a confirmation, not a change.

## 4. Tests

- [x] 4.1 `e2e/test_theme_mode.py`: add `test_error_page_renders_light_in_dark_mode`:
  - store `dark`;
  - abort the lazily loaded `StaffLayout` module with `page.route` (both attempts, so `lazyPage`'s one automatic reload also fails; a page chunk loops forever, see design Risks);
  - open that page and assert the "Something went wrong" heading is visible;
  - assert `<html>` has no `data-theme`;
  - assert the visible header logo image's `src` is the dark-wordmark lockup.
- [x] 4.2 ~~`test_phone_nav_logo_follows_theme`~~ dropped: `MobileNavBar` is only `AppShell`'s fallback, and both layouts pass their own top bar, so no page renders it (design Context). The themed swap stays covered by the brand-identity scenarios through the shared `BrandLogo`.
- [x] 4.3 `e2e/test_responsive_matrix.py`: add a footer check.
  - At 1440px on `/`: the `contentinfo` footer is ≤ 88px tall, and the logo, tagline and copyright share one row (same vertical centre ± 4px).
  - At 360px: the footer's computed top and bottom padding are ≤ 16px, and the page does not scroll horizontally.
- [x] 4.4 Run only the touched e2e modules (`npm run e2e -- test_theme_mode.py test_responsive_matrix.py`), not the full suite. Do not run them while pytest runs in VMSS_API (they share Redis rate limits).

## 5. Verify

- [x] 5.1 `npm run lint` passes (oxlint, brand, grid-span and theme-colour checks) and `npm run build` succeeds.
- [x] 5.2 In the browser, with Dark stored, force the error page and confirm three things: it is light, the header and footer show the full "Guestify" wordmark, and the footer is a single slim row at 1920px. Also check the visitor portal landing, visitor request, track and 404 footers at 360, 768 and 1440px, and the staff phone nav bar logo in Light and Dark.
