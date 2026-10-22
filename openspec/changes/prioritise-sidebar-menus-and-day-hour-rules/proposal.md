## Why

- **Admin sidebar.** The 17 items follow the order the features were
  built in, not how often they are used.
  - The pages admins open every day (Invitations, Calendar) are 13th
    and 14th, below one-time setup such as Floors and Security Gates.
  - On a 720px-tall laptop they sit below the fold of the nav list.
- **Staff and reception sidebars.** "My actions" (register a visitor) is
  the most frequent task at the desk and for hosts, but it is listed
  last.
- **Day view.** Its hour headings are plain labels. Week view separates
  hours with a label on a hairline rule, and staff want the same clear
  hour separation in Day view.

## What Changes

- **Admin sidebar reordered by use and grouped** under small section
  labels:
  - **Operations:** Dashboard, Invitations, Calendar, Audit Trail
  - **People & Access:** Employees, Roles & Permissions
  - **Visitor Setup:** Visitor Categories, Workflows, Form Builder
  - **Organisation:** Branches, Buildings, Floors, Departments, Reception
    Desks, Security Gates, Kiosks, Organisation Configs

  On the collapsed icon rail, the section labels become thin dividers,
  so the rail stays icon-only.
- **Staff and Reception sidebars reordered:** Dashboard, My actions,
  Invitations, Calendar. The labels, routes and the active-item logic
  are unchanged.
- **Day view hour headings use Week view's separator style:** the hour
  label followed by a hairline rule across the card.
  - Busy hours keep a stronger label.
  - Headings stay sticky.
  - The visit cards in Day view keep their full detail.
- No routes, labels, permissions or pages change. Only the order, the
  grouping and the heading style change.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `app-shell`: adds a requirement that the sidebar menus follow a fixed,
  usage-based order, with the Admin sidebar grouped into labelled
  sections.
- `staff-calendar`: adds a requirement that Day view separates hours the
  same way Week view does.

## Impact

- **Sidebars:**
  - `components/AdminSidebar.tsx`: grouped `NAV_SECTIONS` in place of the
    flat `NAV_ITEMS`. The label lookup used by the phone top bar reads
    from the flattened list.
  - `components/DashboardSidebar.tsx`, `components/ReceptionSidebar.tsx`:
    item order.
- **Calendar:** `pages/calendar/components/PagedDayList.tsx`. The Day
  (`detail`) variant uses the hour-rule heading.
- **Tests:** e2e is skipped at the user's request. The reordered menus
  only change position, and existing tests find items by name.
- **API and dependencies:** none.
