## Context

`use-admin-workflow-form.ts` fetches `roles: RoleOut[]` (via `listRolesUseCase`) alongside categories and existing rules. `stepOrder === 0` is already hardcoded as "Reception" throughout the app (`use-invitations-board.ts`'s delegate guard, `VisitRequestCard.tsx`'s `isReceptionStep`, the `reception-dashboard` guard's `isReception` derivation) — all by *position*, never by checking the role's actual name. This form is the only place stepOrder 0's role is *chosen*, and today nothing there enforces it matches what the rest of the app assumes.

## Goals / Non-Goals

**Goals:**
- Level 1's approver is always the "Reception" role, both for new workflows and when editing existing ones (correcting a mismatch on save if one exists).
- A missing "Reception" role in the org's role catalog is a clear, blocking error — not a silent broken state.

**Non-Goals:**
- No change to levels 2+ — still freely assignable to any role.
- No change to the "Reception" role's own definition/permissions (Roles & Permissions page) — this only affects which role Level 1 of a *workflow* points to.
- No backend/API change — same `saveWorkflowUseCase`/rule shape; only the frontend constrains what value Level 1 can hold.

## Decisions

**Resolve "Reception" by case-insensitive name match against the already-fetched `roles` list**, the same convention used everywhere else in the app (`branchRole.roleName.toLowerCase() === 'reception'` in `staff-auth-repository.ts`). No new API call, no new field — reuses data the form already loads.

**Force `levels[0].approverRoleId` to the resolved Reception role's id as soon as `roles` finishes loading, in both create and edit mode** — not only at submit time. This means an edit-mode workflow whose saved Level 1 was some other role visibly shows "Reception" from the moment the page loads, so there's no surprise between what's displayed and what gets saved (per your confirmed decision to force it on save, made honest by also forcing it on display).
- *Alternative considered*: leave the pre-filled value alone in edit mode and only rewrite it at submit time. Rejected — a locked field showing a value that silently changes on save is confusing; what's shown should always be what's saved.

**Level 1's `SelectField` renders with `disabled` and a fixed value, reusing the same `disabled` prop the Visitor Category field already uses in edit mode** — no new component, no new locked-field UI pattern.

**Missing "Reception" role blocks the whole form with the existing `errorMessage` pattern** (same UI slot as the load-failure error state, with a Retry action re-running `load()`), rather than a field-level error — since without that role, no level in the workflow can be validly created regardless of what else the admin does.
- *Alternative considered*: let the admin proceed and leave Level 1 blank/invalid, surfaced only as a submit-time validation error. Rejected — the problem isn't something the admin can fix on this page (the role must be created first, in Roles & Permissions), so failing fast with a clear explanation is more honest than a dead-end validation error after they've filled in the rest of the form.

## Risks / Trade-offs

- **An org that genuinely wants a different role at Level 1 loses that flexibility** → accepted; per Context, the rest of the app already assumes Level 1 is Reception everywhere else, so this isn't removing a capability that safely existed — it's closing a gap where the form allowed a configuration the rest of the app can't actually handle correctly.
- **Silently correcting an existing workflow's Level 1 to Reception on save** (per your confirmed choice) → an admin editing an unrelated field (e.g. adding a Level 3) and saving would also quietly fix a pre-existing Level-1 mismatch. This is the intended behavior, not a bug, but worth the admin noticing — the locked field visibly showing "Reception" (not the old value) from page-load makes the correction visible before they save, not just after.
