## Why

Admins currently have no way to define or manage the organisation's visitor classifications and their compliance policy (NDA requirement, escort requirement, max visit duration, badge color). Today the only place a "visitor category" exists is a hardcoded client-side option list in the visitor registration wizard, with no admin-managed source of truth. The sidebar already reserves a "Visitor Categories" nav slot, but activating it does nothing yet. The Figma design (node `203:1780`, "Visitor Categories Registry") specifies the screen needed to close this gap.

## What Changes

- Add a new **Visitor Categories Registry** admin screen at `/admin/visitor-categories` listing each category's name, description, badge color, NDA requirement, escort requirement, and max visit duration, with per-row Edit and Delete actions.
- Add dedicated **Add Category** (`/admin/visitor-categories/new`) and **Edit Category** (`/admin/visitor-categories/:id/edit`) pages: category name, description, badge color (picked from a fixed palette), NDA requirement (free text), escort requirement (free text), and max duration (free text).
- Wire the reserved `visitor-categories` sidebar item to navigate to the new list page.
- Add the full data layer for visitor categories: domain schema, repository port, infrastructure adapter, use cases (list/create/update/delete), API endpoints, and composition-root wiring, following the existing reception-desks/security-gates pattern.
- Display (non-functional) "Filters" affordance per the design, consistent with how Filters is presented on the other admin register screens.

## Capabilities

### New Capabilities
- `admin-visitor-categories`: Super Admin screen to view, add, edit, and delete visitor categories, each carrying a badge color and compliance policy fields (NDA requirement, escort requirement, max duration).

### Modified Capabilities
(none — no existing capability's requirements change; this does not touch the existing free-text `visitorCategory` field on the visitor registration wizard)

## Impact

- New: `src/domain/entities/visitor-category-schema.ts` (+ `visitor-category-out-schema.ts` wire schema), `src/data/repositories/visitor-category-repository.ts`, `src/data/use-cases/{list,create,update,delete}-visitor-category.ts`, `src/infrastructure/visitor-category-repository.ts`.
- Modified: `src/data/api/api-endpoints.ts` (new `LIST/CREATE/UPDATE/DELETE_VISITOR_CATEGORY` entries), `src/composition-root.ts` (new lazy resolvers + `AppDependencies` entries), `src/App.tsx` (three new routes), `src/presentation/components/AdminSidebar.tsx` (`handleActivate` case for `visitor-categories`).
- New presentation: `src/presentation/pages/admin-visitor-categories/` (list page, form page, `Components/VisitorCategoriesTable.tsx`, a small badge-color swatch picker, `hooks/use-admin-visitor-categories.ts`, `hooks/use-admin-visitor-category-form.ts`), following the `admin-reception-desks`/`admin-security-gates` folder shape.
- No relation to Building, Floor, or Branch — this is a flat, org-wide registry (closer in shape to `admin-host-employees`' role list than to the building-scoped entities).
- Does not change `src/domain/entities/visitor-schema.ts`'s existing free-text `visitorCategory` field or the hardcoded `VISITOR_CATEGORY_OPTIONS` in the visitor registration wizard; wiring the wizard to this new registry is a candidate follow-up, not part of this change.
