## Why

For a reception-only (single total step) invitation, there is no delegated host and no multi-level workflow — Reception is the sole approver for the entire request. Staff viewing the Visitor Info modal for such a request have no indication of who to treat as the point of contact while the host field is unassigned. Since Level 1 of every workflow is enforced to be the Reception role (`lock-workflow-level-one-to-reception`), a reception-only invitation's point of contact is unambiguously Reception.

## What Changes

- The Visitor Info modal SHALL show a "Point of Contact" field with the value "Reception" when the invitation's approval workflow is reception-only (exactly one total step).
- Multi-step workflows are unaffected — no "Point of Contact" field is shown; the existing Host field remains the only relevant contact indicator there.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: the Visitor Info modal shows "Point of Contact: Reception" for reception-only invitations.

## Impact

- **Affected code**:
  - `src/presentation/utils/approval-step-label.ts` — new `resolvePointOfContactLabel(detail, workflowRulesByCategory)` helper, reusing `isReceptionCurrentStep`/`resolveTotalSteps` (the same condition `VisitRequestCard`'s plain "Approve" button already uses for reception-only invitations).
  - `src/presentation/components/invitation-board/VisitorInfoModal.tsx` — new optional `workflowRulesByCategory` prop; renders a "Point of Contact" field in the "Visit details" grid when the label resolves.
  - `src/presentation/pages/admin-invitations/admin-invitations.tsx`, `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` — pass the already-available `workflowRulesByCategory` (from their respective board hooks) into `<VisitorInfoModal>`.
- **Not affected**: no schema, endpoint, or backend change — purely a derived display label from data already fetched for the kanban board.
