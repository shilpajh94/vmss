## Why

The admin and staff sign-in pages now use a modern split-screen design (`modernize-login-pages`). The visitor portal landing page (`/`) still has the older layout: a white header bar, a darkened full-width photo with two white cards, and a white footer bar. It no longer looks like the same product. The landing page is the first screen every visitor sees, so it should share the new Guestify look.

## What Changes

- Rebuild `/` on the same split-screen layout as the sign-in pages:
  - **Brand panel** (left, from 1024px wide): the lobby photo under a navy gradient and the Guestify on-dark logo. It also carries the headline "Welcome to the Visitor Portal", the existing tagline, three visitor-focused highlights, and the copyright line.
  - **Action panel** (right): a "Visitor Portal" tag, a short heading, the two entry points as modern, fully clickable action cards, and the Privacy Policy, Terms of Service and support contact links.
  - **Narrow screens:** the brand panel collapses to the slim navy strip with the logo and tag, as the sign-in pages do.
- The "Request a Visit" card becomes the highlighted primary choice: a cyan accent and a cyan call-to-action. "Track Your Visit" is the secondary, outlined choice. Each card keeps its title, description and call-to-action label ("Request Visit" / "Track Request"), and the whole card is clickable.
- Generalise the sign-in pages' layout into one shared split-screen layout. Each page supplies its own brand copy, footer links and help line, so the landing page, `/admin/login` and `/staff/login` share it without duplicating it. The sign-in pages look exactly as they do now.
- The landing page stops using the shared white `PortalHeader` and `PortalFooter`. The request, track, not-found and error pages keep them unchanged.
- Unchanged:
  - routes and navigation targets;
  - the always-light theme on public pages;
  - configuration-driven policy and support links.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `visitor-portal-landing`:
  - the entry-points requirement now describes cards that are clickable as a whole;
  - the product-identity requirement moves the logo and copyright from the header and footer to the brand panel or top strip. The Guestify and configured-support wording from `rebrand-to-guestify` is carried over;
  - the fits-the-viewport requirement is rewritten for the split layout.
- `responsive-layout`: the "Public Portal Footer Is Compact" requirement no longer lists the landing page among the pages that use the shared footer. Its landing-page scenario moves to the track page.

## Impact

- **Code (VMMS_WEB only):**
  - `src/presentation/pages/visitor-portal-landing/` (page, `ActionCard`; `PortalHero` removed);
  - `src/presentation/components/auth/AuthSplitLayout.tsx`, generalised into a shared split-screen layout;
  - the two sign-in pages need only a prop change.
- **No API changes, no new dependencies.** The public-page download budget must still pass. The landing page now loads the lobby photo only on desktop.
- **Tests:**
  - `e2e/test_responsive_matrix.py::test_public_footer_is_compact` measures the shared footer on `/`, so it must point at `/visitor/track` instead;
  - landing-page navigation is covered by the e2e flows that start from `/`.
- **Other changes:** `rebrand-to-guestify` modifies the same landing identity requirement. This change carries that wording forward and drops the rebrand's superseded delta, as was done for `staff-login`.
