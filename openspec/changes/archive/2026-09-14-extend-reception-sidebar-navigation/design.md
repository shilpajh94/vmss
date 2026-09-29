## Context

`reception-dashboard`'s original design (see its own archived design.md) deliberately gave Reception only a single-item sidebar and left the Visits/Register-Visitor pages untouched. In manual testing, a reception user clicking through to those existing pages landed on the plain staff sidebar (`DashboardSidebar`) with no way back except typing a URL — a real usability gap, not anticipated by the original scope.

Two approaches were tried in sequence during testing:
1. Add a conditional "back to Dashboard" link inside `DashboardSidebar` itself. This worked functionally but produced two different-looking sidebars (`ReceptionSidebar` at 280px vs. `DashboardSidebar` at 260px, different active-item styling) that a Reception user would bounce between — confirmed by the user as the actual complaint ("need one consistent sidebar").
2. Reverted (1); instead, render `ReceptionSidebar` itself, unmodified, on `/staff/dashboard` and `/staff/visitors/new` when the session is Reception, leaving `DashboardSidebar` untouched for everyone else.

## Goals / Non-Goals

**Goals:**
- One consistent sidebar (same component, same look) follows a Reception user across Dashboard, Visits, and Register Visitor.
- No change to `DashboardSidebar` itself, and no change to the Visits board's or Register Visitor wizard's own behavior for non-Reception users.

**Non-Goals:**
- No new pages or routes — `/staff/dashboard` and `/staff/visitors/new` are the same existing pages, just conditionally sidebar-swapped.
- No change to what "My actions" (register a visitor) does — Reception gets the same existing wizard, not a Reception-specific variant.

## Decisions

**Conditional component swap in the page (`currentUser?.isReception ? <ReceptionSidebar .../> : <DashboardSidebar .../>`), not a shared/parameterized sidebar component.**
`ReceptionSidebar` and `DashboardSidebar` already exist as complete, independent components with different item sets. Branching at the call site is a two-line change per page and keeps each sidebar's own code simple; the alternative (a single sidebar component covering both role's nav sets via props) would need to reintroduce cross-cutting complexity into a component this repo's convention keeps simple (see `.claude/rules/clean-architecture.md`'s page/shared-component split) for two call sites only.

**`ReceptionSidebar` gains real nav items ("Visits" → `/staff/dashboard`, "My actions" → `/staff/visitors/new`) rather than staying a single-item sidebar with a "back" affordance.**
This is what makes it the *same* sidebar wherever it renders — no special-casing for "am I on the dashboard or somewhere else."

## Risks / Trade-offs

- **`ReceptionSidebarActiveItem` and `DashboardSidebarActiveItem` now describe overlapping destinations (both have a "visits" and a "my-actions" concept) without a shared type** → acceptable; each sidebar is independently simple, and the two pages already independently decide which one to render based on role.
