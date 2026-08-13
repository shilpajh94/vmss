## Why

The app currently boots to a placeholder home page ("React + Vite + TypeScript architecture shell"). The Figma file "VMS" (node `5:6`, "visitor-portal-landing", on the "visitor web portal" page) defines the actual first screen visitors see: a "VisitorPass" branded landing page with two entry points — request a visit, or track an existing one. Shipping this now replaces the placeholder with the real product surface and gives the two follow-on flows (the multi-step request wizard and the tracking lookup, proposed separately) a page to link from.

## What Changes

- Add a new **Visitor Portal Landing** page: header (logo + wordmark), hero ("Welcome to the Visitor Portal" + supporting copy), two action cards ("Request a Visit" → `Request Visit` button, "Track Your Visit" → `Track Request` button), and a footer (logo, tagline, "Privacy Policy" / "Terms of Service" links, support contact email) — matching the Figma design's copy, layout, and the tokens already established in `src/styles/theme.css`.
- **BREAKING**: replace the root route (`/`)'s placeholder `HomePage` with this landing page. The placeholder `src/presentation/pages/home/` is removed since nothing else references it.
- The two CTA buttons link to `/visitor/request` and `/visitor/track`. Neither route is registered by this change — those pages are proposed separately (per scope decision, this change covers the landing page only). Until those follow-on changes ship, clicking either CTA hits no matching route and renders nothing (React Router's default for an unmatched path); this is an accepted, temporary state.

## Capabilities

### New Capabilities
- `visitor-portal-landing`: the visitor-facing landing page — hero, the two visit-request/track entry points, and footer content.

### Modified Capabilities
- `app-shell`: the "Application renders a routed shell on load" requirement's scenario changes from rendering the placeholder home page to rendering the visitor portal landing page at the root route.

## Impact

- `src/App.tsx`: root route now renders the new landing page instead of `HomePage`.
- `src/presentation/pages/home/`: removed (placeholder, no longer referenced).
- `src/presentation/pages/visitor-portal-landing/`: new page + page-local components.
- No `src/data/`, `src/infrastructure/`, `src/domain/`, or `composition-root.ts` changes — this page has no network calls (the CTAs only navigate; the two request/track features carrying real API integration are separate follow-on changes).
