## 1. Point of contact label

- [x] 1.1 Add `resolvePointOfContactLabel(detail, workflowRulesByCategory)` to `src/presentation/utils/approval-step-label.ts`, returning `'Reception'` when `isReceptionCurrentStep(...)` is true and `resolveTotalSteps(...) <= 1`, else `undefined`.
- [x] 1.2 Thread an optional `workflowRulesByCategory` prop into `VisitorInfoModal`; render a "Point of Contact" field in the "Visit details" grid only when the label resolves.
- [x] 1.3 Pass `workflowRulesByCategory` from `admin-invitations.tsx` and `staff-dashboard.tsx` into `<VisitorInfoModal>` (both already have it in scope from their board hooks).

## 2. Verification

- [x] 2.1 Typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`) pass clean.
- [x] 2.2 Confirm at the code level: a multi-step workflow's Reception step, and any non-Reception step, both resolve `undefined` and render no "Point of Contact" field — same guard (`isReceptionCurrentStep` + `resolveTotalSteps <= 1`) that already gates the plain "Approve" button.
- [ ] 2.3 **Unverified** — not exercised against a live API/real workflow data in this sandbox.
