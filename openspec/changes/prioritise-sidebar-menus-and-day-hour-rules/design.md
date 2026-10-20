## Context

- **Admin sidebar.** `AdminSidebar.tsx` renders a flat `NAV_ITEMS` array
  into `<nav>` through `SidebarNavItem`. The same array feeds the phone
  top bar's page-name lookup (`NAV_ITEMS.find(...)?.label`).
  `isCollapsed` (from `useSidebarCollapse`) already hides the build label
  on the icon rail.
- **Staff and Reception sidebars.** `DashboardSidebar.tsx` and
  `ReceptionSidebar.tsx` each have a four-item `NAV_ITEMS`. The active
  item comes from route prefixes, not from array position, so reordering
  is safe.
- **Hour headings.** `PagedDayList.tsx` has two heading styles:
  - `block` (Week): a label on a hairline rule;
  - `detail` (Day): a plain label on a translucent, blurred bar.

## Goals / Non-Goals

**Goals:**
- One source of truth for each sidebar's order.
- Section labels that cost almost no height and vanish on the rail.
- Day and Week share one hour-heading style.

**Non-Goals:**
- Collapsible sections, per-user custom order, or role-based hiding.
  Every admin still sees every item.
- Changing labels, icons or routes. The duplicate `MonitorIcon` and
  `ShieldIcon` uses stay as they are.

## Decisions

### D1. Admin nav as sections, flattened for lookups

```ts
const NAV_SECTIONS = [
  { label: 'Operations', items: [dashboard, invitations, calendar, audit-trail] },
  { label: 'People & Access', items: [host-employees, roles] },
  { label: 'Visitor Setup', items: [visitor-categories, workflows, form-builder] },
  { label: 'Organisation', items: [branches, buildings, floors, departments,
      reception-desks, security-gates, kiosks, organisation-configs] },
] as const
const NAV_ITEMS = NAV_SECTIONS.flatMap((section) => section.items)
```

- The label lookup and `handleActivate` keep using `NAV_ITEMS`
  unchanged.
- The `<nav>` maps sections. Each section is a `<div role="group"
  aria-label={label}>`.
- **Expanded sidebar:** a section shows its label as `aria-hidden` text,
  because the group's `aria-label` already names it for screen readers.
  The label uses small uppercase `text-sidebar-muted` text with
  `tracking-wide`, `px-3 pt-3 pb-1`, and no top padding on the first
  section.
- **Collapsed rail:** a section shows an `h-px bg-sidebar-line mx-2
  my-2` divider, skipped for the first section.
- `ADMIN_ROUTE_ACTIVE_ITEMS` (prefix → item) is untouched. Its order
  matters only for prefix matching, and no two prefixes overlap.

*Alternative considered:* a flat reorder with no labels. Rejected by the
user's choice. 17 items with no grouping is hard to scan.

### D2. Staff and Reception: reorder the arrays

Move `my-actions` to second place in both `NAV_ITEMS` arrays. Nothing
else depends on the order.

### D3. Day headings reuse the Week heading markup

In `PagedDayList`, render the `block` heading (label + `h-px flex-1
bg-border` rule, sticky, `bg-surface`) for both variants, and delete the
`detail` heading branch.
- Keep a little more vertical padding for `detail` (`py-2` against
  `py-1.5`), so the roomier Day cards don't crowd the rule.
- The card's body has no top padding (fix-paging-footers D5), so the
  sticky heading still sits flush at the scroll area's top edge.

## Risks / Trade-offs

- **[Trade-off]** Admins used to the old order will need a moment to
  re-find setup pages. → The section labels make the new layout easy to
  scan. Item names are unchanged, so browser autocomplete and bookmarks
  are unaffected.
- **[Risk]** e2e tests are skipped at the user's request. → Existing tests
  locate sidebar items by role and name, not position. Lint, build and a
  browser check (rail and expanded, both portals, Day view) cover this
  change.
