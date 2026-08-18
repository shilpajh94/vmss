## Why

The real Figma design for creating a branch (node `206:4`, "Create New Branch") is a dedicated full page with a much richer field set than the modal built in `admin-branches` — it was built without that design available. This change replaces the "Add Branch" modal with that page and expands the branch record to match.

## What Changes

- **BREAKING**: `Branch` gains required fields `country`, `physicalAddress`, `contactEmail`, `contactPhone`, and optional `operatingHoursFrom`, `operatingHoursTo`, `notes`. Existing required fields (`name`, `branchCode`, `locationCity`, `contactPerson`) are unchanged; `contactPerson` remains free text (no employee directory exists yet to back a picker).
- Replace "Add Branch" (previously a modal) with a dedicated page at `/admin/branches/new` matching the Figma design: breadcrumb ("Organisation Admin > Branches > Create New Branch"), "Branch Identity & Geography" section (name, branch code, location/city, country, physical address), "Operations & Administration" section (contact person, contact email, contact phone, operating hours, operational status toggle, internal notes), and Cancel/Create Branch footer actions.
- The Branches list's "Add Branch" button now navigates to `/admin/branches/new` instead of opening a modal. On successful creation, the admin is returned to `/admin/branches` and sees the new branch in the table plus a success toast; on failure they stay on the create page with their entries intact and see an error toast.
- "Edit Branch" stays a modal (no Figma design exists for editing) but is expanded with the same new fields, using the same required-field set as creation, so an admin can edit every field they could set on creation.
- Country and Operating Hours (From/To) become `SelectField`s with hardcoded option lists (the same pattern already used for Timezone in `admin-organisation-configs`), since no country-list or scheduling backend exists.
- The Admin top bar (`AdminTopBar`) gains a breadcrumb-trail mode alongside its existing title/description mode, since the create page's top bar shows a breadcrumb ("Organisation Admin > Branches > Create New Branch") instead of a fixed title and description — the search/notification/profile area on the right is unchanged and still shared.

## Capabilities

### Modified Capabilities
- `admin-branches`: "Add Branch" moves from a modal to a dedicated page with an expanded, required field set; "Edit Branch" keeps its modal but gains the same expanded fields.

## Impact

- **New route**: `/admin/branches/new` in `src/App.tsx`.
- **Changed domain schema**: `src/domain/entities/branch-schema.ts` — `BranchSchema` gains `country`, `physicalAddress`, `contactEmail`, `contactPhone`, `operatingHoursFrom`, `operatingHoursTo` (optional), `notes` (optional).
- **New presentation code**: `src/presentation/pages/admin-branches/admin-branch-create.tsx` (page), `src/presentation/pages/admin-branches/hooks/use-admin-branch-create.ts`.
- **Changed presentation code**: `admin-branches.tsx`'s "Add Branch" button navigates instead of opening the modal; `use-admin-branches.ts` drops its add-mode form state (create no longer happens on this page); `BranchFormModal.tsx` is expanded with the new fields and used only for editing; `AdminTopBar.tsx` gains a breadcrumb-mode prop.
- **No change** to `src/data/repositories/branch-repository.ts`, the use cases, the adapter, or the API endpoints — `create`/`update` already accept/return a full `Branch`, so widening the schema's shape is sufficient; no new endpoints are needed.
- **No backend changes are made by this change** — it assumes the existing `/branches` endpoints accept and return the widened shape.
