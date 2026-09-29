## 1. Reception sidebar gains two more items

- [x] 1.1 In `src/presentation/components/ReceptionSidebar.tsx`, add `'visits'` and `'my-actions'` to `ReceptionSidebarActiveItem`, add their `NAV_ITEMS` entries ("Visits" with `UsersIcon`, "My actions" with `CheckIcon`), and add `handleActivate` branches navigating to `/staff/dashboard` and `/staff/visitors/new` respectively.

## 2. Reuse the Reception sidebar on the existing Visits and Register Visitor pages

- [x] 2.1 In `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`, render `<ReceptionSidebar activeItem="visits" />` instead of `<DashboardSidebar activeItem="all-visitors" />` when `currentUser?.isReception` is true; otherwise unchanged.
- [x] 2.2 In `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx`, render `<ReceptionSidebar activeItem="my-actions" />` instead of `<DashboardSidebar activeItem="my-actions" />` when `currentUser?.isReception` is true; otherwise unchanged.

## 3. Verification

- [x] 3.1 Typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`) all pass clean.
- [x] 3.2 Manually verified in the browser (live testing during this change): a Reception user sees the identical sidebar (Dashboard/Visits/My actions) across all three pages, with the correct item active on each, and can move freely between them.
