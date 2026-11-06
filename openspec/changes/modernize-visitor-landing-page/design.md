## Context

`modernize-login-pages` added `src/presentation/components/auth/AuthSplitLayout.tsx`. Its sign-in-specific content is hard-coded:
- the brand-panel headline, tagline and three highlights;
- the Security Policy / Terms footer links;
- the "Need help? Contact System Administrator" line.

The landing page (`visitor-portal-landing.tsx`) is built differently:
- the shared `PortalHeader` (white, light logo);
- a `HeroImage` backdrop with a `bg-primary/55` overlay;
- `PortalHero` text and two `ActionCard`s whose only clickable part is the button-like `Link`;
- the shared `PortalFooter`, which shows Privacy, Terms and "Support Contact: {email}".

`PortalHeader` and `PortalFooter` are also used by the request, track, not-found and route-error pages.

`check-theme-colors.mjs` exempts `pages/visitor-*` but not `components/`, so the shared layout must keep using theme tokens only.

## Goals / Non-Goals

**Goals:**
- One split-screen layout component behind all three pages, with per-page content passed in.
- `/admin/login` and `/staff/login` render pixel-identical to today after the refactor.

**Non-Goals:**
- Restyling the request wizard, track, not-found or error pages, or the shared `PortalHeader`/`PortalFooter`.
- New copy for the action cards. Titles, descriptions and call-to-action labels stay as they are.

## Decisions

### D1. Generalise `AuthSplitLayout` into `SplitScreenLayout`

Move the layout to `src/presentation/components/layout/SplitScreenLayout.tsx` and give it these props:
- `portalLabel`;
- `brand: { headline: ReactNode; tagline: string; highlights: { label: string; icon: string }[] }`;
- `footerLinks: FooterLink[]`;
- an optional `aside?: ReactNode`, a slot under `children` that the sign-in pages use for the help line;
- `children`.

The pieces that are the same everywhere stay inside the layout:
- the logo and photo gating;
- the mobile strip;
- the scroll container;
- the copyright placement;
- the entrance animation.

`AuthSplitLayout` stays as a thin wrapper. It supplies the current sign-in brand copy, the Security/Terms links and the help line, so the two sign-in pages don't change at all.

The page decides which footer links to show. The landing page passes Privacy and Terms through `footerLinks()`, and adds the "Support Contact: {email}" link when `SUPPORT_EMAIL` is set. That matches the configured-support rule in the identity requirement.

*Alternative considered:* a second, landing-only layout copied from `AuthSplitLayout`. Rejected because this is exactly the duplication the login change removed. Three pages would drift.

### D2. Action panel width and content

The form column is `max-w-[400px]` on sign-in. The landing page passes a wider content width (`max-w-[480px]`) through a `contentClassName` prop, because the cards carry two lines of description.

The landing page's children are:
- a "Welcome" heading with the description "How can we help you today?";
- the two cards, stacked vertically at every width. Side-by-side cards don't fit a half-width panel, and a single column also covers the phone layout.

### D3. Whole-card links

`ActionCard` becomes one `<Link>`. Inside it:
- an icon tile;
- the title, as text in the link, not a heading, so the link's name reads naturally;
- the description;
- a call-to-action row: the label plus an arrow that slides 2px on hover.

The link's accessible name contains both the title and the call-to-action label, so `get_by_role("link", name="Request Visit")` and `name="Track Request"` both resolve by substring.

Variants:
- **Primary:** a cyan border tint, a soft cyan background, and a solid cyan call-to-action pill.
- **Secondary:** a neutral border and an outlined call-to-action.

Both lift 1px on hover with a stronger shadow, using `--motion-fast`. Focus uses the existing `focus-visible` ring convention.

`PortalHero.tsx` is deleted. Its text moves into the brand panel's headline and tagline props.

### D4. Brand copy for visitors

- **Headline:** "Welcome to the Visitor **Portal**." The accent word is cyan, mirroring "securely." on the sign-in pages.
- **Tagline:** the existing "Request a secure entry pass or keep track of your active registrations in real-time."
- **Highlights:**
  - "Pre-register before you arrive";
  - "A QR pass for quick check-in";
  - "Track your request status live".
- **Icons:** inline SVG paths, reusing the calendar, QR and search shapes.

### D5. Absorbing `rebrand-to-guestify`'s landing delta

This change's identity requirement already carries the rebrand's Visimio and configured-support wording. Before this change is synced, delete `rebrand-to-guestify/specs/visitor-portal-landing/` and update its proposal line. The two changes can then archive in either order, the same resolution used for `staff-login`.

## Risks / Trade-offs

- [The refactor could shift the sign-in pages.] → Screenshot `/admin/login` and `/staff/login` at 1920×870 and 360×640 before and after, and compare.
- [`test_public_footer_is_compact` checks the shared footer's logo, tagline and copyright on `/`. The landing page no longer has that footer, so the test fails.] → Point the test at `/visitor/track`, which still uses the shared footer and matches the moved scenario.
- [Cards stacked in a half-width panel may not fit at 1024×700 with long descriptions.] → Use the `short`/`xshort` variants to tighten card padding and gaps. Verify at 1024×700 and 1280×800.
- [Visitors used to the old centred layout.] → Labels and destinations are unchanged, and only the arrangement differs.

## Migration Plan

This is a frontend-only change. Ship with the next web release; roll back by reverting the commit.
