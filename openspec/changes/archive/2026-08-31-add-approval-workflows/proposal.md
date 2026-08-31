## Why

Visitor categories currently have no configurable approval chain: every invitation is approved ad hoc by whoever has the `APPROVE_INVITATION` permission, with no sequential sign-off, no mandatory/optional steps, and no escalation or auto-approve timers. The backend already exposes an `approval-workflow-rules` API (create/list/get/update/delete) that models a workflow as an ordered set of rules scoped to a visitor category, but no admin UI exists to manage it. The Figma "Add Workflow" screen (node 268:72) is the first UI for this: an ordered list of approval levels, each an approver, with add/remove-level controls and Save/Cancel.

## What Changes

- Add a new **Workflows** section to the Organization Admin area: a list page grouping existing approval-workflow rules by visitor category, and an Add/Edit Workflow form page matching the Figma design.
- The Add/Edit Workflow form extends the Figma mock with a **Visitor Category** selector (required) at the top of the card, since the backend has no standalone "workflow" entity — a workflow is the set of rules sharing one `visitorCategoryId`. This is an intentional deviation from the literal Figma mock, agreed with the requester.
- Each approval level's **Approver Select** lists organisation **roles** (via the existing `/auth/roles` endpoint and `ListRolesUseCase`), not individual employees — the backend's `approverRoleId` field is role-scoped, unlike the placeholder employee names ("John Smith", etc.) shown in the Figma mock.
- Saving a workflow reconciles the form's ordered level list against the visitor category's existing rules: creates rules for new levels, updates rules whose approver/order changed, and deletes rules for removed levels — each level's `stepOrder` is derived from its position in the list.
- Add a new **Workflows** entry to the Admin sidebar, and routes `/admin/workflows`, `/admin/workflows/new`, `/admin/workflows/:visitorCategoryId/edit`.
- Wire the new `/approval-workflow-rules` endpoints end-to-end: `API_ENDPOINTS` entries, a domain schema, an `ApprovalWorkflowRuleRepository` port, an `HttpApprovalWorkflowRuleRepository` adapter, and use cases, following the existing admin-CRUD pattern (see `admin-visitor-categories`, `admin-security-gates`).

## Capabilities

### New Capabilities
- `admin-approval-workflows`: Super Admin's Workflows list (grouped by visitor category) and Add/Edit Workflow page, for configuring each visitor category's ordered, role-based approval chain.

### Modified Capabilities
(none — no existing capability's requirements change; the Admin sidebar gaining a new item is additive and not separately specified per-item elsewhere)

## Impact

- **New files**: `src/domain/entities/approval-workflow-rule-schema.ts`, `src/data/repositories/approval-workflow-rule-repository.ts`, `src/infrastructure/approval-workflow-rule-repository.ts`, `src/data/use-cases/{list,save}-approval-workflow-rules.ts` (or similar), `src/presentation/pages/admin-workflows/**`.
- **Modified files**: `src/data/api/api-endpoints.ts` (new `*_APPROVAL_WORKFLOW_RULE(S)` entries), `src/composition-root.ts` (new repository/use-case wiring + `AppDependencies` fields), `src/presentation/components/AdminSidebar.tsx` (new nav item), `src/App.tsx` (new routes).
- **Backend**: none — consumes the existing `/api/v1/approval-workflow-rules` endpoints as-is (confirmed against the live OpenAPI spec at `https://vmss-new-api.ddev.site:8443/openapi.json`).
- **Reused**: `ListRolesUseCase` / `/auth/roles` (approver options), `VisitorCategoryRepository` / `/visitor-categories` (category options and list-page grouping).
