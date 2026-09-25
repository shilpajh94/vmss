## 1. `ErrorState` component

- [ ] 1.1 Create `components/ui/ErrorState.tsx` with `{ message, onRetry }`
      props, reproducing the exact shared class string and retry button
      markup used by the 17 current duplicated blocks.
- [ ] 1.2 Diff each of the 17 call sites individually against
      `ErrorState`'s output; migrate every site whose markup matches
      exactly: `admin-buildings.tsx`, `admin-departments.tsx`,
      `admin-branches.tsx`, `admin-floors.tsx`,
      `admin-security-gates.tsx`, `admin-reception-desks.tsx`,
      `admin-workflows.tsx`, `admin-visitor-categories.tsx`,
      `admin-roles.tsx`, `admin-role-create-form.tsx`,
      `admin-role-permissions-form.tsx`, `admin-host-employees.tsx`,
      `admin-organisation-configs.tsx`, `admin-audit-trail.tsx`,
      `admin-dashboard.tsx`, `staff-dashboard.tsx`,
      `reception-dashboard.tsx`. Leave any site with a genuine extra
      element un-migrated and note it.
- [ ] 1.3 `npm run dev` and visually confirm the error/retry state on at
      least 3 migrated pages looks pixel-identical to before.

## 2. `StatusBadge` component

- [ ] 2.1 Create `components/ui/StatusBadge.tsx` with
      `{ active, activeLabel?, inactiveLabel? }` props, reproducing the
      shared Active/Inactive markup and colors.
- [ ] 2.2 Migrate the 6 identically-shaped call sites:
      `BuildingsTable.tsx`, `DepartmentsTable.tsx`, `BranchesTable.tsx`,
      `FloorsTable.tsx`, `HostEmployeesTable.tsx`,
      `WorkflowListTable.tsx`.
- [ ] 2.3 Individually check `SecurityGatesTable.tsx` and
      `ReceptionDesksTable.tsx`'s differently-shaped local badge maps;
      migrate only if they represent the same two visual states as
      `StatusBadge`, otherwise leave as-is and note why.
- [ ] 2.4 Visually confirm badge rendering is unchanged on all migrated
      tables.

## 3. `FormPageHeader` component

- [ ] 3.1 Create `FormPageHeader` with `{ title, onBack }` props,
      reproducing the shared back-button markup, placed alongside other
      page-chrome primitives.
- [ ] 3.2 Migrate the 8 call sites: `admin-building-form.tsx`,
      `admin-department-form.tsx`, `admin-reception-desk-form.tsx`,
      `admin-host-employee-form.tsx`, `admin-floor-form.tsx`,
      `admin-workflow-form.tsx`, `admin-security-gate-form.tsx`,
      `admin-visitor-category-form.tsx`.
- [ ] 3.3 Visually confirm header/back-button behavior is unchanged on
      each migrated form page.

## 4. `text-field-label` design token

- [ ] 4.1 Add a `text-field-label` (or equivalent) token to
      `styles/theme.css` using the `#475569` value.
- [ ] 4.2 Replace the local `#475569` class-string constants in
      `admin-building-form.tsx`, `admin-workflow-form.tsx`,
      `admin-security-gate-form.tsx`, `admin-reception-desk-form.tsx`,
      `admin-department-form.tsx`, `admin-visitor-category-form.tsx`,
      `admin-host-employee-form.tsx` with the new token, preserving each
      file's existing weight/casing utility (`font-semibold` vs.
      `font-bold uppercase`) unchanged.
- [ ] 4.3 Visually confirm field labels are unchanged on all 7 pages.

## 5. `moveItem` drag-reorder helper

- [ ] 5.1 Check whether dnd-kit's own `arrayMove` utility is already
      available as a transitive dependency; if so, use it directly and
      skip writing a new helper.
- [ ] 5.2 Otherwise, add a `moveItem<T>(items, activeId, overId, getId)`
      helper in a shared utils location.
- [ ] 5.3 Replace the three duplicated `handle*DragEnd` bodies in
      `FieldPropertiesPanel.tsx`, `admin-form-builder-step-editor.tsx`,
      and `admin-form-builder.tsx` with calls to the helper (or
      `arrayMove`).
- [ ] 5.4 Manually test drag-reorder in the form builder (options, steps,
      and step-list) to confirm identical behavior.

## 6. Visitor form entry unification

- [ ] 6.1 Create a shared module hoisting the common field list and a
      factory function generic over the `customFieldValues` value type.
- [ ] 6.2 Update `visitor-request/types.ts` to use the shared
      shape/factory in place of `VisitorFormEntry`/
      `createEmptyVisitorFormEntry`.
- [ ] 6.3 Update `staff-visitor-registration/types.ts` to use the shared
      shape/factory in place of `StaffVisitorFormEntry`/
      `createEmptyStaffVisitorFormEntry`.
- [ ] 6.4 Confirm both the visitor pre-registration flow and the staff
      visitor registration flow still build and submit forms correctly.

## 7. Pagination schema dedup

- [ ] 7.1 Replace the inline pagination object shape with
      `PaginationMetaSchema` in each of the 13 files:
      `branch-out-schema.ts`, `floor-out-schema.ts`,
      `employee-out-schema.ts`, `building-out-schema.ts`,
      `department-out-schema.ts`, `reception-desk-out-schema.ts`,
      `security-gate-out-schema.ts`, `visitor-category-out-schema.ts`,
      `role-out-schema.ts`, `permission-out-schema.ts`,
      `employee-directory-out-schema.ts`,
      `visit-request-summary-schema.ts`,
      `approval-workflow-rule-schema.ts`.
- [ ] 7.2 Run the TypeScript build (`tsc`/`npm run build`) and confirm no
      type errors from the schema swap.
- [ ] 7.3 Spot-check one list page per schema group still paginates
      correctly against a live/dev API response.

## 8. `DepartmentsTable` memoization

- [ ] 8.1 Wrap `DepartmentsTable.tsx`'s `new Map(employees.map(...))` in
      `useMemo(() => ..., [employees])`.
- [ ] 8.2 Confirm the department table still renders employee lookups
      correctly after an edit/add/remove cycle.

## 9. Current-user context and auth-guard consolidation

- [ ] 9.1 Add `CurrentUserContext`, populated once in
      `AdminLayoutContent` from its existing
      `getCurrentStaffUserUseCase.execute()` call.
- [ ] 9.2 Move the `sessionStorage.getItem('token')` redirect-to-login
      check into `AdminLayoutContent` as a `useEffect` that runs before
      rendering protected content, preserving the exact redirect target
      and `replace: true` behavior.
- [ ] 9.3 Remove the now-redundant `sessionStorage` guard from the 28
      individual `use-admin-*` hooks (and `staff-visitor-registration.tsx`
      if applicable).
- [ ] 9.4 Remove the dead `getCurrentStaffUserUseCase.execute()` call from
      the 12 hooks that never consume its result: `use-admin-buildings.ts`,
      `use-admin-departments.ts`, `use-admin-branches.ts`,
      `use-admin-floors.ts`, `use-admin-reception-desks.ts`,
      `use-admin-security-gates.ts`, `use-admin-workflows.ts`,
      `use-admin-host-employees.ts`, `use-admin-roles.ts`,
      `use-admin-visitor-categories.ts`,
      `use-admin-organisation-configs.ts`, `use-admin-audit-trail.ts`.
- [ ] 9.5 Update `admin-dashboard`'s hook to read the current user from
      `CurrentUserContext` instead of fetching its own copy, adding a
      loading-state guard if the context value can be unresolved when the
      hook first renders.
- [ ] 9.6 Confirm: (a) an unauthenticated visit to any `/admin/*` route
      still redirects to `/admin/login`, (b) the top bar and
      `admin-dashboard`'s greeting still show the correct user name, (c)
      network tab shows the `/auth/me`-equivalent call firing once per
      admin session load, not once per 15-second poll tick on every page.

## 10. `AdminListPageShell`

- [ ] 10.1 Create `AdminListPageShell` accepting the page's computed
      `{ isLoading, error, isEmpty, onRetry }` plus `header`, `filters`,
      and table `children` slots, using `ErrorState`/`LoadingState`/
      `EmptyState` internally.
- [ ] 10.2 Adopt it in `admin-buildings.tsx`, confirming identical
      rendered shell (header, filters, loading/error/empty states, table,
      pagination) before moving to the next page.
- [ ] 10.3 Adopt it in `admin-departments.tsx`.
- [ ] 10.4 Adopt it in `admin-branches.tsx`.
- [ ] 10.5 Adopt it in `admin-floors.tsx`.
- [ ] 10.6 Adopt it in `admin-security-gates.tsx`.
- [ ] 10.7 Adopt it in `admin-reception-desks.tsx`.
- [ ] 10.8 Adopt it in `admin-workflows.tsx`.
- [ ] 10.9 Adopt it in `admin-visitor-categories.tsx`, replacing its
      bespoke text-labeled pagination footer with the shared `Pagination`
      component per the shell's standard composition.

## 11. Final verification

- [ ] 11.1 Run the full TypeScript build and lint (`npm run build`,
      project's lint script) and confirm clean.
- [ ] 11.2 Run any existing test suite and confirm it passes unmodified
      in assertions (only updated where it asserted on now-extracted
      markup verbatim).
- [ ] 11.3 Manually walk each of the 11 admin list pages, each of the 8
      form pages, the form builder's drag-reorder, and one full
      visitor-registration flow (public + staff) in the dev server to
      confirm no visible or functional regression.
