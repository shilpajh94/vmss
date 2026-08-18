## 1. Domain schema

- [x] 1.1 Widen `src/domain/entities/branch-schema.ts`'s `BranchSchema`: add required `country`, `physicalAddress`, `contactEmail`, `contactPhone`; add optional `operatingHoursFrom`, `operatingHoursTo`, `notes`

## 2. Shared UI: AdminTopBar breadcrumb mode

- [x] 2.1 Extend `src/presentation/components/AdminTopBar.tsx` to accept either `description: string` (existing) or `breadcrumb: { label: string; isActive?: boolean }[]` (new), rendering a breadcrumb trail (with `>` separators, the active segment in the admin-accent color) on the left when `breadcrumb` is provided instead of the title/description pair

## 3. Create Branch page

- [x] 3.1 Add `src/presentation/pages/admin-branches/hooks/use-admin-branch-create.ts`: holds the create-page form values, exposes `updateField`, `submit` (validates required fields, calls `createBranchUseCase.execute`, on success navigates to `/admin/branches` and toasts success, on failure toasts error and keeps the entered values), and `cancel` (navigates to `/admin/branches` without creating)
- [x] 3.2 Add `src/presentation/pages/admin-branches/admin-branch-create.tsx`: renders `AdminSidebar` (`activeItem="branches"`), `AdminTopBar` in breadcrumb mode ("Organisation Admin > Branches > Create New Branch"), the page header ("Create New Branch" + description), a form card with "Branch Identity & Geography" (Branch Name, Branch Code, Location/City, Country, Physical Address) and "Operations & Administration" (Contact Person, Contact Email, Contact Phone, Operating Hours From/To, Operational Status toggle, Internal Notes) sections, and Cancel/Create Branch footer actions
- [x] 3.3 Add hardcoded option lists for Country (short list, "United Kingdom" first) and Operating Hours (hourly increments, `hh:mm AM/PM`, 6:00 AM–10:00 PM), used by both the create page and the edit modal

## 4. Branches list and Edit modal updates

- [x] 4.1 In `use-admin-branches.ts`, drop `add` from `BranchFormState` (now `{ mode: 'edit'; branch: Branch } | undefined`) and remove `openAddForm`/create-branch handling from `saveBranch` (it now only updates)
- [x] 4.2 In `admin-branches.tsx`, change the "Add Branch" button to `navigate('/admin/branches/new')` instead of opening the modal
- [x] 4.3 Expand `BranchFormModal.tsx` with the same field set as the create page (Country, Physical Address, Contact Email, Contact Phone, Operating Hours From/To, Internal Notes) alongside the existing fields, using the option lists from 3.3, for editing only

## 5. Routing

- [x] 5.1 Add the `/admin/branches/new` route to `src/App.tsx` rendering the create page

## 6. Verification

- [x] 6.1 Run the dev server and visually compare `/admin/branches/new` against the Figma design (node `206:4`) for layout, spacing, sections, and color fidelity
- [x] 6.2 Manually verify: Add Branch navigates to the create page, validation on required fields, successful creation navigates back to the list with the new branch visible and a success toast, failed creation keeps entered values with an error toast, Cancel returns to the list without creating
- [x] 6.3 Manually verify: Edit modal opens pre-filled with every field (including the new ones) and successfully updates a branch
- [x] 6.4 Confirm `admin-organisation-configs`'s top bar (description mode) still renders correctly after the `AdminTopBar` breadcrumb-mode extension
- [x] 6.5 Run lint/type-check and any existing test suite
