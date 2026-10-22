## Why

The visitor portal landing page (`/`) scrolls vertically on a normal laptop or desktop browser window. On a 1920×1080 screen (about 866px of usable viewport), the footer sits below the fold, so visitors have to scroll to see the rest of a page that has nothing to scroll for. The cause is fixed vertical spacing that adds up to roughly 980px of content: hero `md:pt-20 md:pb-16`, card row `lg:pb-[100px]`, and the 72px header plus about 165px of footer. The page's `min-h-screen` wrapper then grows past the viewport.

## What Changes

- On desktop-width screens (`lg`+) with a viewport height of at least 800px, the landing page fits in one viewport: header, hero, both action cards and footer are all visible with no vertical scrollbar.
- The hero section (background image + overlay) stretches to fill the height between the header and footer. The hero text and action cards are centred vertically in that space, instead of being pushed down by fixed top and bottom padding.
- The fixed `md:pt-20 md:pb-16` hero padding and `lg:pb-[100px]` card-row padding become smaller, consistent spacing, so on tall screens the extra height goes into the stretched hero, not into empty space.
- Phone and tablet layouts, and short desktop viewports (under 800px tall), keep their current behaviour. The page grows with its content and scrolls normally. Nothing gets clipped.
- No change to card content, routes, copy, header, or the shared `PortalFooter` component, which the request and track pages also use.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `visitor-portal-landing`: adds a requirement that the landing page fits in a single desktop viewport without scrolling, and that it falls back to normal scrolling (never clipping) on viewports too small to hold it.

## Impact

- `src/presentation/pages/visitor-portal-landing/visitor-portal-landing.tsx`: page layout (flex sizing, card-row padding).
- `src/presentation/pages/visitor-portal-landing/Components/PortalHero.tsx`: hero padding.
- `src/presentation/pages/visitor-portal-landing/Components/ActionCard.tsx`: only if the vertical budget needs a small `lg` padding trim (see design.md).
- No API, routing, dependency or shared-component changes. Web-only; VMSS_API is unaffected.
