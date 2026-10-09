## 1. Shared fixes

- [x] 1.1 Add `gap-page-section` to `RouteTransition`'s wrapper (design.md Decision 1).
- [x] 1.2 Update `BrandLogo` to `max-w-fit object-contain object-left`, keeping the caller's height. Add `self-start` in `PortalFooter` (design.md Decision 2).
- [x] 1.3 In `responsive-table.ts`, let the first column wrap below `md` (min width 8rem), and give the pinned actions column a left border and shadow (design.md Decision 3).

## 2. Page-level fixes

- [x] 2.1 `RegistrationWorkspaceHeader`: remove the horizontal padding so the title aligns with the card.
- [x] 2.2 Create Branch (and the branch edit modal, if it shares the row): render "Operational Status" as a standard field, with the label on top and the switch plus state text on one row, top-aligned with the notes field.
- [x] 2.3 `AdminTopBar` below `md`: show the active breadcrumb label, or "Dashboard" when there is none. Move `initialsFor` to `presentation/utils/initials.ts`, and show initials in the admin and reception top-bar avatars.

## 3. Verification

- [x] 3.1 Add `scripts/screenshot-pages.py` (from `assets/shoot.py`: env-driven base URL and credentials, output to gitignored `screenshots/`, non-zero exit on horizontal scroll), and document the docker command in the README (design.md Decision 5).
- [x] 3.2 Run it at 375, 768 and 1440px. Compare against `assets/before-*.png`:
  - footer logo at its natural ratio;
  - 16/24px gaps on the dashboard, Visits and Create Branch;
  - Register Visitor aligned;
  - Branches status visible at 375px;
  - top bar showing the page name and initials.

  Remove any page-local `mt-*` that now double-spaces.
- [x] 3.3 `npm run build` and `npm run lint` are clean.
