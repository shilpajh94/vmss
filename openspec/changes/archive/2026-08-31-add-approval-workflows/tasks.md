## 1. Domain schema

- [x] 1.1 Create `src/domain/entities/approval-workflow-rule-schema.ts`: `ApprovalWorkflowRuleSchema` (`id`, `visitorCategoryId`, `stepOrder`, `approverRoleId`, `isMandatory`, `escalationMinutes` nullable, `autoApproveMinutes` nullable, `isActive`), `ApprovalWorkflowRule` type, and `ApprovalWorkflowRuleInput` (`Omit<ApprovalWorkflowRule, "id" | "isActive">`).
- [x] 1.2 Add `ApprovalWorkflowRuleResponseSchema` (single-item envelope) and `ApprovalWorkflowRuleListResponseSchema` (paginated envelope, matching `visitor-category-out-schema.ts`'s shape) to the same file or an adjacent `-out-schema.ts` file, whichever matches this repo's existing single-vs-out-schema split for camelCase-only APIs.

## 2. API endpoints, port, and adapter

- [x] 2.1 Add `LIST_APPROVAL_WORKFLOW_RULES` (GET `/approval-workflow-rules`), `CREATE_APPROVAL_WORKFLOW_RULE` (POST `/approval-workflow-rules`), `UPDATE_APPROVAL_WORKFLOW_RULE` (PUT `/approval-workflow-rules/:id`), `DELETE_APPROVAL_WORKFLOW_RULE` (DELETE `/approval-workflow-rules/:id`) to `src/data/api/api-endpoints.ts`, all `hasToken: true`.
- [x] 2.2 Create port `src/data/repositories/approval-workflow-rule-repository.ts`: `ApprovalWorkflowRuleRepository` with `list(visitorCategoryId?: string)`, `create(input)`, `update(id, input)`, `remove(id)`.
- [x] 2.3 Create adapter `src/infrastructure/approval-workflow-rule-repository.ts`: `HttpApprovalWorkflowRuleRepository implements ApprovalWorkflowRuleRepository`, using `ApiClient.makeRequest` + the endpoints/schemas from 2.1/1.2 (list passes `queryParams: { visitorCategoryId, pageSize: 100 }` when filtering).

## 3. Use cases

- [x] 3.1 Create `src/data/use-cases/list-approval-workflow-rules.ts`: `ListApprovalWorkflowRulesUseCase`, constructor-injected `ApprovalWorkflowRuleRepository`, `execute(visitorCategoryId?: string)` delegating to `repository.list(...)`.
- [x] 3.2 Create `src/data/use-cases/save-workflow.ts`: `SaveWorkflowUseCase`, constructor-injected `ApprovalWorkflowRuleRepository`, `execute(visitorCategoryId, levels: { approverRoleId: string }[])` implementing the reconciliation algorithm from `design.md` (fetch existing rules for the category, index-diff against submitted levels, issue minimal create/update/remove calls).
- [x] 3.3 Create `src/data/use-cases/delete-workflow.ts`: `DeleteWorkflowUseCase`, constructor-injected `ApprovalWorkflowRuleRepository`, `execute(ruleIds: string[])` removing every given rule id.

## 4. Composition root wiring

- [x] 4.1 In `src/composition-root.ts`, add a lazy `resolveApprovalWorkflowRuleRepository()` resolver (adapter over the shared `ApiClient`).
- [x] 4.2 Add lazy resolvers for `ListApprovalWorkflowRulesUseCase`, `SaveWorkflowUseCase`, `DeleteWorkflowUseCase`, and expose all three (plus the roles and visitor-category use cases already available) on `AppDependencies`.

## 5. Presentation — Workflows list page

- [x] 5.1 Create `src/presentation/pages/admin-workflows/hooks/use-admin-workflows.ts`: loads rules (`listApprovalWorkflowRulesUseCase`, no filter) and visitor categories, groups rules by `visitorCategoryId` joined to category name, exposes loading/error/retry, and pending-delete/confirm/cancel state (deleting a group calls `deleteWorkflowUseCase` with that group's rule ids, then removes it from local state) plus toast notifications on success/failure.
- [x] 5.2 Create `src/presentation/pages/admin-workflows/Components/WorkflowGroupList.tsx` (or table, matching the closest existing list component's structure) rendering one group per visitor category with its ordered levels (approver role name) and per-group Edit/Delete actions.
- [x] 5.3 Create `src/presentation/pages/admin-workflows/admin-workflows.tsx`: `AdminSidebar activeItem="workflows"`, `AdminTopBar` (description matching the Figma copy), "Add Workflow" button, error/loading/empty states (`EmptyState`, `LoadingState`) matching `admin-security-gates.tsx`'s structure, `ConfirmDialog` for delete.

## 6. Presentation — Add/Edit Workflow page

- [x] 6.1 Create `src/presentation/pages/admin-workflows/hooks/use-admin-workflow-form.ts`: resolves edit-vs-create from the `:visitorCategoryId` route param; loads visitor categories (filtered to unconfigured ones in create mode), roles, current staff user, and — in edit mode — the category's existing rules (sorted by `stepOrder`) to pre-fill levels; holds ordered `levels` state (`{ approverRoleId: string | null }[]`, starting with one empty level in create mode); exposes `addLevel`, `removeLevel` (no-op on the last remaining level, renumbers on removal), `updateLevelApprover`, `updateCategory`, validation errors, `submit` (calls `saveWorkflowUseCase.execute`), and `cancel` (navigate back to `/admin/workflows`).
- [x] 6.2 Create `src/presentation/pages/admin-workflows/admin-workflow-form.tsx` matching the Figma "Add Workflow" layout: back button + "Add Workflow"/"Edit Workflow" title, Visitor Category select above the "Approval Levels" card (card header/subtitle "Staff will approve sequentially in the order listed below"), one row per level (numbered badge, `SelectField` of roles, delete/trash button), "+ Add Level" button, Cancel/Save Workflow actions.

## 7. Routing and navigation

- [x] 7.1 Add `'workflows'` to `AdminSidebarActiveItem`, `NAV_ITEMS` (with a suitable icon), and `handleActivate` in `src/presentation/components/AdminSidebar.tsx`.
- [x] 7.2 Add routes to `src/App.tsx`: `/admin/workflows` → `AdminWorkflowsPage`, `/admin/workflows/new` → `AdminWorkflowFormPage`, `/admin/workflows/:visitorCategoryId/edit` → `AdminWorkflowFormPage`.

## 8. Verification

- [x] 8.1 Run `npm run lint` and `tsc -b` (via `npm run build`) and fix any errors.
- [x] 8.2 Started the dev server and drove it headlessly (Playwright + the already-installed local Chromium): confirmed the sidebar renders "Workflows" active with the correct icon, the top bar shows the Figma copy, and both `/admin/workflows` and `/admin/workflows/new` render their page shell, error state, and "Try again" retry without an unhandled exception when the backend call fails — screenshots reviewed. Full happy-path walk (create → list → edit → delete against real data) was not run because it requires real staff login credentials against `https://vmss-new-api.ddev.site:8443`, which weren't available in this session; recommend a manual pass with real credentials before merging.
- [x] 8.3 Manually verify an unauthenticated browser is redirected from `/admin/workflows` and `/admin/workflows/new` to `/admin/login`. Verified headlessly: both routes redirect to `/admin/login`.
