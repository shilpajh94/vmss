## 1. Foundations

- [x] 1.1 Add `presentation/hooks/use-media-query.ts` (`matchMedia` + `useSyncExternalStore`) with a `useIsDesktop()` helper for `(min-width: 1024px)`.
- [x] 1.2 Make `p-page-content` (16/24/32px) and `gap-page-section` (16/24px) responsive in `src/styles/theme.css` (design.md Decision 7).
- [x] 1.3 Add a `useFocusTrap(ref, active)` hook (trap Tab, Escape callback, restore focus on deactivate).

## 2. Responsive shell

- [x] 2.1 Add `NavDrawerContext` and drawer state to `AppShell`: an off-canvas sidebar below `lg`, a backdrop button, body scroll lock, closing on route change and on resize to `lg`, and focus trapping (design.md Decision 2).
- [x] 2.2 Update `AdminSidebar`, `DashboardSidebar`, and `ReceptionSidebar`: width `min(280px,85vw)` below `lg`, a `lg:hidden` close button in the header, and `closeNav()` on item click.
- [x] 2.3 Add a `lg:hidden` menu button (with `aria-expanded`/`aria-controls`) to `AdminTopBar` and `ReceptionTopBar`. Add a minimal top bar with the menu button for `StaffLayout` pages that have none.
- [x] 2.4 Compact the top bars below `md`: truncate the breadcrumb/title, hide the description and last-refreshed label, `px-4 md:px-8`, single row.
- [x] 2.5 Refactor `reception-dashboard.tsx` to render through `AppShell` (keeping `ReceptionTopBar` and the role gate) instead of its own `min-h-screen` layout.
- [x] 2.6 Make `PortalHeader` (`px-4 md:px-12`) and `PortalFooter` (stacked columns on phone) responsive, and check `PublicLayout`.

## 3. Shared UI primitives

- [x] 3.1 `ui/Modal` + `ConfirmDialog`: full width with `p-2` outer margin (or a bottom sheet) below `sm`, `max-h-[100dvh]`/`90dvh`, a scrolling body, and a sticky header/footer actions row.
- [x] 3.2 `TextField`, `TextareaField`, `SelectField`, `AutocompleteField`, `DropdownFilter`: `text-base` on phone (no iOS zoom), full width on phone, and a ≥40px control height below `lg`.
- [x] 3.3 `Checkbox`, `ToggleSwitch`, `SegmentedToggle`, icon buttons, `Pagination`: ≥40×40 tap area below `lg`. Pagination wraps at 360px.
- [x] 3.4 `PageContentLayout` and the shared list-page header: wrap the title/actions row, stack search + filters full-width on phone.
- [x] 3.5 `dashboard/KpiRow` (1 → 2 → 4 columns), `RecentCheckinsCard` / `UpcomingVisitorsCard` (contained table scroll, priority columns).

## 4. Admin list pages (tables)

- [x] 4.1 Branches, buildings, floors, departments: contained-scroll wrapper, `hidden md:table-cell` on non-essential columns, sticky row-actions cell, and hover-only actions made tap-visible below `lg` (design.md Decision 4).
- [x] 4.2 Reception desks, security gates, kiosks, host employees: same treatment.
- [x] 4.3 Roles, visitor categories, workflows, audit trail (fix its 6 fixed widths): same treatment.
- [x] 4.4 Admin dashboard, admin invitations, and organisation configs: fluid containers and wrapping headers.

## 5. Admin create/edit forms

- [x] 5.1 Replace `w-[1160px]` with `w-full max-w-[1160px]` in the 9 admin form pages, and collapse their grids to `grid-cols-1 md:grid-cols-2 lg:grid-cols-N`. Keep the Save/Cancel row visible and wrapping.
- [x] 5.2 `admin-branch-create` and the other remaining create/edit views (roles, organisation configs): same treatment, reviewing each fixed width individually (design.md Decision 8).
- [x] 5.3 Form builder: stack the steps list / field list / properties panel on phone and tablet, wrap the header toolbar, make `w-64` search `w-full sm:w-64`, and stack `AddFieldModal`'s grids.
- [x] 5.4 Form builder DnD: add `TouchSensor` (`delay: 200, tolerance: 5`) next to `PointerSensor` at all 3 `useSensors` sites, and confirm drag handles are ≥40px on touch.

## 6. Staff and reception pages

- [x] 6.1 Staff dashboard board: below `lg`, a status selector (segmented control or scrollable chips with counts) that renders only the active `KanbanColumn` full-width. The desktop row is unchanged, with no refetch on switch (design.md Decision 5).
- [x] 6.2 Apply the same board treatment on the reception side wherever it renders `KanbanColumn`.
- [x] 6.3 `VisitRequestCard`: wrap its meta rows and give its action buttons tap size. `VisitorInfoModal` / `EditInvitationModal` / `Reschedule` / `Deny` / `Delegate` modals stack their grids to 1 column on phone.
- [x] 6.4 Staff visitor registration: fix the fixed width, and stack `PrimaryContactCard`'s 3 grids and the dynamic-field grids (`dynamic-fields/*`, including the `RepeatableFieldGroup` table → contained scroll).
- [x] 6.5 Staff login and staff SSO login: full-width card on phone, and responsive gateway/portal headers.

## 7. Public visitor pages

- [x] 7.1 Visitor portal landing: single-column hero/cards on phone, and fix its 3 fixed widths.
- [x] 7.2 Visitor request wizard: add `StepProgressHeader` (current label, "Step X of N", progress bar, jump back to completed steps) below `md`, keep `StepSidebar` at `md` and up, and fed both from the same step list (design.md Decision 6).
- [x] 7.3 Wizard steps (`VisitorFieldsForm`, `VisitInfoStep`, `VehicleInfoStep`, `ReviewConfirmStep`, OTP and history views): single-column grids below `sm`, fixing the 6 fixed widths. Use a `sticky bottom-0` Back/Next/Submit footer below `md`.
- [x] 7.4 Visitor track: full-width lookup form + `StatusPanel` (stacked grid), fixing its 4 fixed widths.

## 8. Verification

- [x] 8.1 `npm run build` (`tsc -b`) and `npm run lint` (oxlint) are clean.
- [ ] 8.2 Check every route in browser devtools at 360×740, 390×844, 768×1024, 1024×768, and 1440×900. Confirm: no horizontal page scroll, all actions reachable, drawer open/close/Escape/route-change, board selector, wizard progress header, and modals fitting.
- [ ] 8.3 At 1440×900, compare each touched page against its pre-change look, where desktop must be unchanged.
- [ ] 8.4 Real-device spot check (one Android phone, one iPhone/iPad or simulator): input focus doesn't zoom, form-builder touch drag works, and the drawer focus trap works with a screen reader.
