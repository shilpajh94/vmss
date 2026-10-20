## 1. Admin sidebar sections (app-shell "Sidebar menus are ordered by how often they are used", design D1)

- [x] 1.1 In `AdminSidebar.tsx`, replace `NAV_ITEMS` with `NAV_SECTIONS` (Operations, People & Access, Visitor Setup, Organisation, in the spec's item order) and derive `NAV_ITEMS` by flattening it for the label lookup
- [x] 1.2 Render each section as `role="group"` with an `aria-label`; show an `aria-hidden` muted uppercase label when expanded, and a thin `bg-sidebar-line` divider on the collapsed rail (none for the first section)

## 2. Staff and Reception order (design D2)

- [x] 2.1 Reorder `NAV_ITEMS` in `DashboardSidebar.tsx` and `ReceptionSidebar.tsx` to Dashboard, My actions, Invitations, Calendar

## 3. Day view hour headings (staff-calendar "Day view separates hours like Week view", design D3)

- [x] 3.1 In `PagedDayList.tsx`, use the label-on-hairline-rule heading for both variants (`py-2` for `detail`) and remove the old `detail` heading branch; update the comment

## 4. Checks

- [x] 4.1 Run `npx tsc -b`, `npm run lint` and `npm run build`
- [x] 4.2 Check in the browser: the admin sidebar shows the four sections expanded and dividers on the rail, the active item still follows the route (e.g. `/admin/floors/new` → Floors), the staff and reception sidebars read Dashboard, My actions, Invitations, Calendar, and Day view's hour headings match Week's (sticky, with the busy hour stronger); e2e is skipped at the user's request
