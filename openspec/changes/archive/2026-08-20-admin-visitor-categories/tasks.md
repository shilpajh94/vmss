## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/visitor-category-schema.ts`: `VisitorCategorySchema` (`id`, `name`, `description?`, `badgeColor: "blue" | "orange" | "gold" | "grey"`, `ndaRequired?`, `escortRequired?`, `maxDuration?`), `VisitorCategory` type, and `VisitorCategoryInput = Omit<VisitorCategory, "id">`.
- [x] 1.2 Add `src/domain/entities/visitor-category-out-schema.ts`: `VisitorCategoryOutSchema`/`VisitorCategoryResponseSchema`/`VisitorCategoryListResponseSchema`, following `security-gate-out-schema.ts`.

## 2. API endpoints

- [x] 2.1 Add `LIST_VISITOR_CATEGORIES` (`GET /visitor-categories`), `CREATE_VISITOR_CATEGORY` (`POST /visitor-categories`), `UPDATE_VISITOR_CATEGORY` (`PUT /visitor-categories/:id`), `DELETE_VISITOR_CATEGORY` (`DELETE /visitor-categories/:id`) to `src/data/api/api-endpoints.ts`, all `hasToken: true`.

## 3. Repository port and adapter

- [x] 3.1 Add `src/data/repositories/visitor-category-repository.ts` port: `list(): Promise<VisitorCategory[]>`, `create(input: VisitorCategoryInput): Promise<VisitorCategory>`, `update(id: string, input: VisitorCategoryInput): Promise<VisitorCategory>`, `remove(id: string): Promise<void>`.
- [x] 3.2 Add `src/infrastructure/visitor-category-repository.ts` implementing the port via `ApiClient.makeRequest` + `VisitorCategorySchema` (no relation lookups needed — no building/floor joins).

## 4. Use cases

- [x] 4.1 Add `src/data/use-cases/list-visitor-categories.ts`, `create-visitor-category.ts`, `update-visitor-category.ts`, `delete-visitor-category.ts`, each constructor-injected with `VisitorCategoryRepository`.

## 5. Composition root wiring

- [x] 5.1 Add lazy resolvers for the visitor-category repository and use cases in `src/composition-root.ts`, and expose `listVisitorCategoriesUseCase`, `createVisitorCategoryUseCase`, `updateVisitorCategoryUseCase`, `deleteVisitorCategoryUseCase` on `AppDependencies`.

## 6. Visitor Categories list page

- [x] 6.1 Add `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-categories.ts`: loads current user + visitor categories, exposes loading/error/retry, delete-with-confirmation flow, and success/error toasts, following `use-admin-security-gates.ts`.
- [x] 6.2 Add `src/presentation/pages/admin-visitor-categories/Components/VisitorCategoriesTable.tsx`: columns for Category Name, Description, Badge Color (colored swatch + palette name), NDA Required, Escort Required (emphasized when the text indicates "always required"), Max Duration, Actions (Edit/Delete), following `SecurityGatesTable.tsx`'s shape.
- [x] 6.3 Add `src/presentation/pages/admin-visitor-categories/admin-visitor-categories.tsx`: renders `AdminSidebar` (`activeItem="visitor-categories"`), `AdminTopBar` (Visitor-Categories-specific `description`), header with "Add Category" button and inert "Filters" control, the table, shared empty state (zero categories) and error state (load failure) per `admin-security-gates.tsx`.

## 7. Add/Edit Category page

- [x] 7.1 Add `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-category-form.ts`: loads current user; detects edit mode via `useParams<{ id: string }>`; validates required `name`; calls create/update use case; success/error toasts; navigates back to the list on success or cancel. No relation data to load (no buildings/floors).
- [x] 7.2 Add `src/presentation/pages/admin-visitor-categories/Components/BadgeColorField.tsx`: a small labeled swatch picker (Blue/Orange/Gold/Grey) rendering each option as a colored square using the matching theme token class (`bg-info`, `bg-warning`, `bg-vip`, `bg-text-muted`).
- [x] 7.3 Add `src/presentation/pages/admin-visitor-categories/admin-visitor-category-form.tsx`: presentational page with Category Name, Description (textarea), Badge Color (`BadgeColorField`, default Blue), NDA Required text field, Escort Required text field, Max Duration text field, Save/Cancel, driven entirely by the hook.

## 8. Routing and navigation

- [x] 8.1 Register `/admin/visitor-categories`, `/admin/visitor-categories/new`, `/admin/visitor-categories/:id/edit` routes in `src/App.tsx`.
- [x] 8.2 Add the `if (key === 'visitor-categories') navigate('/admin/visitor-categories')` case to `handleActivate` in `src/presentation/components/AdminSidebar.tsx`.

## 9. Verification

- [x] 9.1 Manually verify: list loads/empty/error states, add category (name validation + success + failure-retains-values), edit category (pre-fill + success + failure), delete (confirm/cancel/success/failure), badge color swatch renders per selection, "Required (Always)" escort emphasis renders distinctly, Filters is inert — against the Figma design (node `203:1780`).
