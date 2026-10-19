## Context

The page wrapper in `visitor-portal-landing.tsx` is `flex min-h-screen flex-col justify-between`. Its content height is set by fixed padding, not by the viewport. Approximate heights at `lg`:

| Block | Height |
|---|---|
| `PortalHeader` | 72px |
| `PortalHero` (`md:pt-20` + title + 2-line body + `md:pb-16`) | ~276px |
| Card row (cards ~370px + `lg:pb-[100px]`) | ~470px |
| `PortalFooter` (`md:py-10` + 3 lines) | ~165px |
| **Total** | **~983px** |

That's above the user's ~866px viewport, so `min-h-screen` grows and the page scrolls. Only ~150px of the overflow is padding that does nothing. `PortalFooter` is shared with `/visitor/request` and `/visitor/track`.

## Goals / Non-Goals

**Goals:**
- No vertical scroll at `lg`+ widths with viewport height ≥ 800px.
- The hero background fills whatever height is left. Content is centred in it on tall screens.

**Non-Goals:**
- Fitting viewports under 800px tall (for example, 1366×768 laptops with browser chrome, about 650px usable). The header, footer and cards alone take ~600px. Fitting would mean shrinking the cards or footer enough to change the design, so these viewports keep scrolling.
- Any change to `PortalFooter`, `PortalHeader`, or other portal pages.

## Decisions

1. **Stretch the hero region with flexbox instead of fixed heights.** The wrapper becomes `flex min-h-dvh flex-col`. The hero region (background + text + cards) becomes `flex-1` with its content centred vertically (`justify-center`), and the footer follows it. The page is never shorter than the viewport. On tall screens the extra height goes into the hero, so there's no blank band. Content that doesn't fit makes the page grow and scroll, which meets the "never clip" scenario.
   - *Alternative rejected:* `h-screen overflow-hidden` at `lg`. Guarantees no scrollbar, but silently clips the footer or cards on short desktop windows.
   - *`dvh` over `vh`:* `min-h-dvh` follows the visible viewport on mobile browsers with collapsing toolbars. Tailwind v4 supports it natively.

2. **Replace the large fixed padding with modest symmetric padding.** Hero: `md:pt-20 md:pb-16` → roughly `pt-10 pb-8` (keep mobile `pt-12 pb-10` or similar). Card row: `lg:pb-[100px]` → roughly `lg:pb-10`. New total at `lg` is about 72 + (40 + 132 + 32) + (370 + 40) + 165 ≈ 851px. That fits 866px but not 800px.

3. **Trim the cards slightly at `lg` only if needed to reach 800px.** To close the remaining ~50px gap, reduce `ActionCard` padding to `lg:p-6` and its internal gap to `lg:gap-5` (about −24px), and tighten hero spacing toward `pt-8 pb-6`. Final values are tuned during implementation against the 1280×800 scenario. This is the one place where tuning by eye is expected.
   - *Alternative rejected:* a `compact` prop on `PortalFooter`. That would put a landing-page concern on a shared component when card and hero spacing already provide enough room.

4. **Optional height-aware spacing.** If a single spacing set can't both fit 800px and look balanced at 1080px, use Tailwind's arbitrary height variant (`[@media(min-height:900px)]:pt-16`) to give taller screens more breathing room. Still flexbox-centred, so this is cosmetic.

## Risks / Trade-offs

- [Hero text and cards sit closer together than before on full-HD screens] → On tall screens the centred layout spreads the leftover space evenly above and below, so the page doesn't look cramped. Compare before and after screenshots at 1920×1080 before merging.
- [Font loading or text wrapping changes the height (for example, the hero body wraps to 3 lines on narrower `lg` widths around 1024px)] → Verify at 1024×800 as well as 1280×800. If it overflows, the page just scrolls; it never clips.
- [The 800px threshold is an estimate based on measured spacing, not a hard CSS breakpoint] → The spec scenarios are the acceptance bar. Check them in the browser at each listed size.
