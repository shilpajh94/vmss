## Context

`StaffLoginPage` (`src/presentation/pages/staff-login/staff-login.tsx`) is a `min-h-screen` flex column: header, then `main` (`flex-1`, `py-12 md:py-[120px]`), then footer. Because `min-h-screen` only sets a floor, the page grows to fit its content, and the content is too tall:

| Part | Approx. height at ≥ md |
|---|---|
| `StaffGatewayHeader` (`py-5` + logo) | ~92px |
| `main` vertical padding (`md:py-[120px]`) | 240px |
| `LoginFormCard` (`md:p-12`, `md:gap-8`, badge, title, 2 fields, 2 buttons, divider, footer line) | ~640px |
| `main` gap + "Need help?" line | ~52px |
| `StaffLoginFooter` (`py-6`) | ~70px |
| **Total** | **~1,094px** vs ~870px visible |

The 240px of fixed padding alone accounts for the overflow. The project uses Tailwind v4 (`@tailwindcss/vite`), so there is no `tailwind.config` `screens` entry. Height-based breakpoints are written as arbitrary variants or as a `@custom-variant` in CSS.

## Goals / Non-Goals

**Goals:**
- The page is exactly one viewport tall when content fits (see the spec scenarios for the target sizes).
- When content does not fit, overflow scrolls inside `main` and never on the whole page.

**Non-Goals:**
- Redesigning the card, changing copy, or changing any login behaviour.
- `/staff/login` (`staff-sso-login.tsx`). The same pattern applies there, but it belongs in a separate change (see proposal).
- Extracting a shared "gateway shell" component for both login pages. This is worth doing once `/staff/login` gets the same fix, but it is premature for one page.

## Decisions

### 1. Pin the shell to the viewport: `h-dvh` with `min-h-screen` fallback and an internally scrolling `main`

Root: `relative flex h-dvh w-full flex-col overflow-hidden`. Header and footer: `shrink-0`. `main`: `flex-1 min-h-0 overflow-y-auto`.

- `dvh` follows the visible viewport on mobile browsers, whose URL bar changes `vh`. No `h-screen` fallback: Tailwind v4 already requires browsers that support `dvh`, and the order of the generated CSS (not class order) would decide between the two.
- `min-h-0` is required. Without it, a flex child keeps its content height and `overflow-y-auto` never takes effect, so the page overflows again.
- **Alternative considered:** keep `min-h-screen` and only shrink the padding. That fixes the 1920×870 case but the page still scrolls whenever content exceeds the viewport, and the footer scrolls away with it. The spec requires header and footer to stay in place, so this is not enough.
- **Alternative considered:** `position: fixed` header and footer. This needs hard-coded offsets for content, and those break as soon as the header wraps on narrow widths (it uses `flex-wrap`).

### 2. Center with a safe-centering inner wrapper, not `justify-center` on the scroller

If `main` scrolls and also has `justify-center`, overflowing content is cut off at the top and cannot be reached, because centered flex overflow spills in both directions. Instead, `main` contains one inner `div` with `flex min-h-full flex-col items-center justify-center gap-…`. When content fits, `min-h-full` centers it. When it doesn't, the wrapper grows and `main` scrolls from the top.

- **Alternative considered:** `justify-safe-center` / `align-content: safe center`. Tailwind v4 has `justify-center-safe`, and browser support is now good. The wrapper pattern is still easier to reason about and works without relying on that newer value. Either is acceptable during implementation, provided the short-viewport scenario passes.

### 3. Replace fixed padding with small padding; two height tiers for spacing

- `main` (inner wrapper) padding: `py-6 md:py-8`. The 240px is no longer needed because centering distributes the free space.
- Two height-based variants are declared once in `src/styles/index.css`: `@custom-variant short (@media (max-height: 900px))` and `@custom-variant xshort (@media (max-height: 800px))`. Named variants were chosen over inline `[@media(max-height:…)]` arbitrary variants because the rules span four files.
- Tall screens (over 900px) keep the approved `md:p-12` / `md:gap-8` card.
- `short`: the card uses `md:p-8` / `md:gap-6`.
- `xshort`: the card uses `py-6` and `gap-4`, with tighter inner gaps (`gap-2` for the title block, `gap-3` for the fields). The wrapper uses `py-4` / `gap-3`. `StaffGatewayHeader` and `StaffLoginFooter` drop to `py-3`.
- **Why these thresholds** (measured in headless Chromium against the production build, not estimated). An initial 860/760 split left 1366×768 overflowing by 50px, and 1920×870 overflowing by 44px once validation errors showed. At 900/800, every target size fits with no scrolling. That includes 1920×870 with both field errors, and about 1533×697, which is the reporter's 1920×870 screen at 125% OS scaling. Below that, overflow scrolls inside `main` as designed.

### 4. Keep the background static against the root

The background `div` stays `absolute inset-0` on the root. The root is now exactly viewport-height with `overflow-hidden`, so the image always covers the viewport and is no longer stretched to the scrolled content height (it currently stretches to about 1,100px).

## Risks / Trade-offs

- [`overflow-hidden` on the root hides something that was meant to overflow, such as a toast or a dropdown] → Toasts render in a `fixed` `ToastViewport` owned by `ToastProvider` at the app root (outside this page's tree), and the page has no popovers. Verify by triggering a failed login and checking that the error notification is visible.
- [Browser autofill or a password-manager icon adds height to the inputs] → The ~50px headroom in the 870px budget absorbs this. Worst case, `main` scrolls internally, which is still within the spec.
- [Height breakpoint numbers are estimates] → Tasks include measuring at 1920×870, 1366×768, 1280×720, and 360×640 in devtools and adjusting the breakpoint value.
