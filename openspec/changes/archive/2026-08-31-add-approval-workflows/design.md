## Context

See `proposal.md` - Why/What Changes for motivation. Relevant existing pieces this design reuses as-is:

- Backend API (confirmed against `https://vmss-new-api.ddev.site:8443/openapi.json`): `POST/GET /api/v1/approval-workflow-rules`, `GET/PUT/DELETE /api/v1/approval-workflow-rules/{rule_id}`. A rule is `{ id, visitorCategoryId, stepOrder, approverRoleId, isMandatory, escalationMinutes, autoApproveMinutes, isActive }`; list supports `visitorCategoryId`, `sortBy` (`step_order`|`created_at`), `sortOrder`, `page`, `pageSize`, and returns a paginated envelope. There is no "workflow" entity — a workflow is the set of rules sharing one `visitorCategoryId`.
- `ListRolesUseCase` (`src/data/use-cases/list-roles.ts`) already calls `LIST_ROLES` (`/auth/roles`) and returns `RoleOut[]` (`{ id, name, ... }`) — reused unmodified for the Approver Select options.
- `VisitorCategoryRepository.list()` (`src/infrastructure/visitor-category-repository.ts`) already calls `LIST_VISITOR_CATEGORIES` — reused unmodified for the Visitor Category select and for the list page's grouping.
- The `admin-visitor-categories` and `admin-security-gates` pages are the closest existing structural precedent (list page + separate create/edit form page, `Components/`, `hooks/use-admin-*`) and this feature follows the same file layout under `src/presentation/pages/admin-workflows/`.

## Goals / Non-Goals

**Goals:**
- Wire the existing `/approval-workflow-rules` API end-to-end following the repo's data-api-layer pattern (endpoints → domain schema → port → adapter → use cases → composition-root → hook → page).
- Present the Figma "Add Workflow" screen faithfully for the parts it shows (approval-level list, add/delete level, Save/Cancel), while adding the Visitor Category field the API requires.
- Support create, edit, and delete of a category's whole rule set (not per-rule CRUD in the UI) from one cohesive "workflow" concept in the admin UI.

**Non-Goals:**
- No UI for `isMandatory` (optional steps), `escalationMinutes`, or `autoApproveMinutes` — every rule is created mandatory with no timers (see spec: "Levels are created without escalation, auto-approve, or optional-step settings"). Revisit in a follow-up change if the product needs it.
- No drag-to-reorder; the only way to change a level's order is delete-and-re-add in the desired position (matches the Figma mock, which has no drag handles).
- No standalone "workflow" backend entity or migration — this change only adds a client-side grouping concept over existing per-rule records.
- No changes to how invitations are actually routed through approval steps at runtime (that's the existing `ApproveInvitationUseCase` / invitation-approval flow); this change only manages the rule configuration.

## Decisions

**Domain schema — one schema, camelCase, matches the wire contract 1:1.** The API already returns/accepts camelCase (`visitorCategoryId`, `stepOrder`, `approverRoleId`, ...), so `ApprovalWorkflowRuleSchema` in `src/domain/entities/approval-workflow-rule-schema.ts` mirrors it directly with `z.infer` — no snake_case mapping layer needed (contrast with `visitor-category-schema.ts`, which does map because that API is snake_case-free but has nullable-vs-optional differences). `id` and `isActive` are server-assigned/managed; a `ApprovalWorkflowRuleInput` type (`Omit<ApprovalWorkflowRule, "id" | "isActive">`) is used for create/update bodies.

**Repository shape — one port, five methods, no per-rule use cases beyond list.** `ApprovalWorkflowRuleRepository`:
```
list(visitorCategoryId?: string): Promise<ApprovalWorkflowRule[]>
create(input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
update(id: string, input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
remove(id: string): Promise<void>
```
`list()` with no argument (all rules) backs the Workflows list page's grouping; `list(visitorCategoryId)` backs the Edit page's pre-fill. Pagination is handled inside the adapter by requesting a large `pageSize` (matching the existing `LIST_VISITOR_CATEGORIES` adapter's `{ pageSize: 100 }` convention) rather than exposing pagination controls in the UI — the admin-facing rule count per organisation is expected to be small (categories × levels).

**Use cases — two, matching the two page-level operations, not one per HTTP call.** Per the repo's use-case pattern (constructor-injected port, `execute`), two use cases are enough because the interesting logic is the reconciliation, not the individual HTTP verbs:
- `ListApprovalWorkflowRulesUseCase.execute(visitorCategoryId?)` → delegates straight to `repository.list(...)`.
- `SaveWorkflowUseCase.execute(visitorCategoryId, levels: { id?: string; approverRoleId: string }[])` → loads the category's current rules, diffs by position against `levels`, and issues the minimal set of `create`/`update`/`remove` calls (see "Save reconciliation algorithm" below). This keeps the diff/reconciliation logic in the `data/` layer (testable, no React), not duplicated inside a presentation hook.
- Delete-workflow (the list page's per-category "Delete") doesn't need its own use case class: the hook calls `listApprovalWorkflowRulesUseCase` output already in memory to know which rule ids belong to the category, then calls the repository's `remove` for each directly through a small `DeleteWorkflowUseCase.execute(ruleIds: string[])` for symmetry with the pattern (constructor-injected port, one method) rather than reaching into the repository from presentation.

**Save reconciliation algorithm** (in `SaveWorkflowUseCase`):
1. Fetch existing rules for the category, sorted by `stepOrder`.
2. Zip the submitted `levels` array (in form order) against the existing rules by index.
3. For index `i` with both a submitted level and an existing rule: if the level's `approverRoleId` differs from the rule's, `update(existingRule.id, { ...same fields..., stepOrder: i + 1, approverRoleId: level.approverRoleId })`; if `stepOrder` alone differs (existing rules reused but reordered), update just that. If nothing differs, skip (no-op call).
4. For index `i` with a submitted level but no existing rule at that index (list grew): `create({ visitorCategoryId, stepOrder: i + 1, approverRoleId: level.approverRoleId, isMandatory: true, escalationMinutes: null, autoApproveMinutes: null })`.
5. For an existing rule with no corresponding submitted level (list shrank): `remove(existingRule.id)`.
6. Run creates/updates/removes with `Promise.all` per group (order between groups doesn't matter — they touch disjoint rule ids); a rejection surfaces to the hook as a single failure (see spec: "Workflow update failure keeps the admin on the page").

This index-based diff (rather than matching by approver identity) is intentionally simple: it treats the level list purely as an ordered sequence, matching how the form presents and edits it (no per-level "this is the same approval step, just moved" tracking beyond position). Alternative considered: track a stable client-side key per level row and diff by key instead of index — rejected as unnecessary complexity, since the UI has no reordering (only delete-and-re-add), so position and identity coincide in practice.

**List-page grouping is computed client-side.** `list()` with no filter returns all rules across all categories; the hook groups them by `visitorCategoryId` and joins against `VisitorCategoryRepository.list()` for each group's display name. No new backend aggregation endpoint is needed.

**New-workflow category options exclude already-configured categories.** The Add Workflow page's Visitor Category options are `allCategories - categoriesWithRules` (computed from the same two lists the list page already loads, refetched on the form page). This enforces the spec's "no duplicate workflow per category" rule by construction rather than by a save-time uniqueness check.

**Routing and sidebar.** New routes `/admin/workflows` (list), `/admin/workflows/new` (create), `/admin/workflows/:visitorCategoryId/edit` (edit) — using the visitor category id as the route param, since that's the only stable identifier for "a workflow" (there's no rule-set id). `AdminSidebar`'s `AdminSidebarActiveItem` union and `NAV_ITEMS`/`handleActivate` gain a `'workflows'` entry, following the exact pattern of every other entry.

## Risks / Trade-offs

- **[Risk]** The reconciliation algorithm's index-based diff means reordering two levels by deleting and re-adding them (rather than a hypothetical drag-to-reorder) always produces one `create` + one `remove` instead of a single `update`, since the deleted level's rule id is gone by the time the new one is added. → **Mitigation**: acceptable — no functional difference to the admin, and Non-Goals already excludes drag-to-reorder in this change.
- **[Risk]** No optimistic locking: if two admins edit the same category's workflow concurrently, the second save's diff is computed against a snapshot that may be stale, and could resurrect or drop a level the first admin already changed. → **Mitigation**: out of scope for this change (no other admin page in this codebase handles concurrent-edit conflicts either); acceptable given this is a low-traffic, single-organisation admin screen.
- **[Risk]** Fetching "all rules" with a large `pageSize` for the list page's grouping doesn't scale indefinitely. → **Mitigation**: acceptable at expected scale (categories × levels is small); revisit if/when the backend adds a grouped-by-category endpoint.
