## Why

`reception-dashboard` (archived) shipped with a single-item sidebar ("Dashboard" only). During manual testing, the reception user needed to reach the existing Visits board and Register Visitor wizard too, and expected the same sidebar to follow them there rather than switching to the plain staff sidebar mid-session.

## What Changes

- The Reception sidebar gains two more items — "Visits" (→ `/staff/dashboard`) and "My actions" (→ `/staff/visitors/new`) — alongside the existing "Dashboard" item.
- `/staff/dashboard` and `/staff/visitors/new` (the existing Visits board and Register Visitor wizard) now render the same Reception sidebar, with the matching item marked active, when the signed-in user has the Reception role — instead of the plain staff sidebar. Non-reception users on those pages are unaffected.

## Capabilities

### Modified Capabilities
- `reception-dashboard`: The sidebar requirement is updated from a single "Dashboard" item to three items (Dashboard, Visits, My actions), and a new requirement describes that this same sidebar (not the plain staff one) renders on the Visits and Register Visitor pages for a Reception-role session.
- `staff-dashboard`: The "renders the sidebar" requirement is qualified — a Reception-role session sees the Reception sidebar (with "Visits" active) instead of the staff sidebar described there.

## Impact

- **Affected code**:
  - `src/presentation/components/ReceptionSidebar.tsx` — add `'visits'` and `'my-actions'` items.
  - `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` — render `ReceptionSidebar` (`activeItem="visits"`) instead of `DashboardSidebar` when `currentUser?.isReception`.
  - `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx` — same conditional swap, `activeItem="my-actions"`.
  - `openspec/specs/reception-dashboard/spec.md`, `openspec/specs/staff-dashboard/spec.md` — updated per above.
- **Not affected**: `staff-visitor-registration`'s own spec already describes its sidebar generically ("matching the dashboard"), so it accommodates this without a delta. No data/use-case/endpoint changes — same routes, same pages, only which sidebar component renders for a Reception session.
- **Status**: Already implemented and verified (typecheck/lint/build clean) during live testing; this change documents that work.
