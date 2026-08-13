## Context

`src/App.tsx` currently registers a single route (`/`) rendering the placeholder `HomePage` from `src/presentation/pages/home/`. `src/styles/theme.css` already carries the Figma-derived color and typography tokens (`--color-primary`, `--color-text-muted`, `text-h1`, `text-body`, etc. — see the archived `apply-figma-theme` change). Source: Figma file `jXdJ0LuzcPY9YxgrnqXle6`, node `5:6` ("visitor-portal-landing"). See `proposal.md` for why this replaces the placeholder now.

## Goals / Non-Goals

**Goals:**
- Landing page matches the Figma layout/copy using the existing token set and Tailwind utilities — no new design tokens needed.
- Page composition follows the established `presentation/pages/<feature>/` + `Components/` convention.

**Non-Goals:**
- Wiring the CTA destinations to working pages — `/visitor/request` and `/visitor/track` are unregistered routes until their respective follow-on changes land.
- Any data fetching, forms, or API calls — this page is static content plus two navigations.
- Promoting the header/footer to shared components — the visitor-request and track-visit pages (proposed separately) will very likely reuse the same header/footer, but a shared abstraction is deferred until that second consumer actually exists.

## Decisions

### Route ownership: landing page replaces `/`, not a new path
The current `/` route renders a placeholder that literally says "architecture shell" — it isn't a real destination. Since the visitor portal landing page is the actual first screen of this product, it replaces `HomePage` at `/` rather than living at a side path like `/visitor`. This is why `app-shell`'s routed-shell requirement is a MODIFIED delta, not left alone.

**Alternative considered**: keep `HomePage` at `/` and add the landing page at a new path (e.g. `/portal`). Rejected — it would leave two competing "home" experiences with no reason for a visitor to ever see the placeholder.

### CTA links target unregistered routes; no stub pages
The "Request Visit" and "Track Request" buttons render as `react-router` `Link`s to `/visitor/request` and `/visitor/track`. Neither route is registered by this change. Per the scope decision, the request wizard and tracking lookup are separate follow-on changes that will register their own routes.

**Alternative considered**: add placeholder "Coming soon" stub pages for both routes now, so the links always resolve to something. Rejected — that's scope creep for a change whose only job is the landing page, and the stub content would just be thrown away the moment the real follow-on change lands.

### Component structure: page-local components, not shared yet
Header, hero, the two action cards, and footer are built as components under `src/presentation/pages/visitor-portal-landing/Components/`, not `src/presentation/components/`. They are highly likely to be reused verbatim by the request-wizard and track-visit pages (same header/footer appear in every screen of the Figma file), but until that second real consumer exists, promoting them to shared components is premature — see Non-Goals.

### No new domain/data/infrastructure code
This page has no backend interaction; it is pure presentation. `composition-root.ts` and `AppDependencies` are untouched.

## Risks / Trade-offs

- **Dead-looking CTAs until follow-on changes ship** → Clicking either button currently navigates to a route with no matching `<Route>`, so `Routes` renders nothing (blank content area, header/footer of the *next* page don't exist yet — actually the whole page unmounts since there's no matching route at all). Mitigation: this is a short-lived, known state; the two follow-on changes are the very next planned work.
- **Header/footer duplication once the next two pages land** → until promoted to shared components, the wizard and tracking pages will (correctly, per YAGNI) copy this markup rather than import it. Mitigation: flag the promotion explicitly as a task in whichever follow-on change lands second.

## Migration Plan

1. Build the new page and its components.
2. Swap `src/App.tsx`'s `/` route to the new page; delete `src/presentation/pages/home/`.
3. No data migration, no feature flag — static content swap, ships in one step.
