## Context

`brand.ts` is the single source of the product name and logos, and every
surface reads from it through `<BrandLogo>`/`BRAND_NAME`. A rename is
therefore mostly asset replacement plus a few literals that cannot import
the module (HTML title, service worker, e2e). The lint chain includes
`scripts/check-brand.mjs`, which currently *forbids* "Visimio"; it must be
flipped in the same change or lint fails.

The open `rebrand-to-guestify` change (tasks largely ticked, never archived)
is replaced by this one. Main specs are mixed: `brand-identity` still says
Visimio while `staff-login`/`staff-sso-login` already say Guestify.

## Goals / Non-Goals

**Goals:** every user-visible "Guestify" becomes "Visimio"; assets renamed and
replaced; guard inverted; no stray Guestify outside archive.
**Non-Goals:** layout/design changes, API/data changes, implementing the
mobile app (separate repo), rewriting archived changes.

## Decisions

1. **PNG 1x/2x logos, as before the Guestify rebrand.** The backend script was
   reverted to PNG output and the SVG master was removed, so the web restores
   `src2x`/`srcSet` in `brand.ts`/`BrandLogo` and drops the SVG favicon.
2. **Assets come from the backend script**, not hand-drawn. Run
   `build_brand_assets.py --web-out` from `VMSS_API`. If the Visimio master
   is not available, ask the backend owner before proceeding. Use `git mv`
   so history follows the renamed SVGs.
3. **Invert the guard** to `/VisitorPass|Guestify/i` and update its header
   comment and error message. Visimio is no longer a retired name.
4. **Docs/specs strategy:** deltas against main specs for the three
   capabilities. `rebrand-to-guestify` is deleted (not archived) so it can
   never sync Guestify wording into main specs. The in-flight
   modernize-* changes get a find/replace of Guestify → Visimio, including
   the "G pin"/"Gu"+"estify" descriptions in their text.
5. **Rename leftovers outside brand.ts:** the service worker keeps its own
   `'Visimio'` literal (it can't import the module).
6. **Mobile** is tracked as a hand-off checklist in tasks, since its repo is
   outside this workspace.

## Risks / Trade-offs

- Mixed names for users until web, mobile and backend deploy → release together.
- Favicon caching hides the new icon → verify in a private window.
- Logos look different (different mark shape and wordmark colour split) →
  re-check every logo slot at 375/768/1440px as in the prior rebrand.
- Browser/CDN cache of old hashed asset names is not a concern (Vite hashes).

## Open Questions

- Is the Visimio logo master/script output available now, or does the backend
  owner need to run it?
- Where does the mobile app repo live, and who owns that change?
