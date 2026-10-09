## 1. Resolve the Reception role and pin Level 1

- [x] 1.1 In `src/presentation/pages/admin-workflows/hooks/use-admin-workflow-form.ts`'s `load()`, after `roles` is fetched, resolve `receptionRole = roleList.find((role) => role.name.toLowerCase() === 'reception')`. If not found, set `errorMessage` to a clear message (e.g. "A 'Reception' role must exist in Roles & Permissions before a workflow can be configured.") and stop before setting `levels` — same early-return shape as the existing catch block's error path.
- [x] 1.2 When `receptionRole` is resolved, force `levels[0].approverRoleId` to `receptionRole.id` in both branches of `load()` (new workflow: `EMPTY_LEVEL` becomes `{ approverRoleId: receptionRole.id }`; edit mode: after mapping `existingRules` to levels, overwrite index 0's `approverRoleId` regardless of what the saved rule had).
- [x] 1.3 In `updateLevelApprover(index, approverRoleId)`, ignore calls where `index === 0` (defensive — the UI won't offer a way to trigger this once Level 1's select is disabled, but the guard keeps the invariant even if something else calls it).
- [x] 1.4 In `removeLevel(index)`, refuse `index === 0` unconditionally, in addition to the existing "don't remove the last remaining level" check.
- [x] 1.5 In `submit()`'s validation, skip the "Approver is required" check for index 0 (it's always set once `receptionRole` resolves) — validate only levels after it.

## 2. Lock Level 1 in the form UI

- [x] 2.1 In `src/presentation/pages/admin-workflows/admin-workflow-form.tsx`, pass `disabled` to Level 1's `SelectField` (`index === 0`), so it renders locked showing "Reception".
- [x] 2.2 Disable the "Remove level" button for `index === 0` regardless of `levels.length` (currently `disabled={levels.length <= 1}` — change to `disabled={index === 0 || levels.length <= 1}`).

## 3. Verification

- [x] 3.1 Run typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`); confirm clean. *(All three pass clean.)*
- [x] 3.2 Confirm at the code level: a new workflow's Level 1 is pre-set to the Reception role's id and its select is disabled from first render. *(`load()`'s else-branch sets `levels` to `[{ approverRoleId: receptionRole.id }]`; the form's Level 1 `SelectField` has `disabled={index === 0}`.)*
- [x] 3.3 Confirm at the code level: editing an existing workflow whose saved Level 1 approver is not Reception displays Level 1 as Reception (not the saved value), and submitting saves that correction. *(`load()`'s edit-mode branch always overwrites `existingLevels[0]` with `{ approverRoleId: receptionRole.id }` after mapping the saved rules, regardless of what was saved; `submit()` sends `levels` as-is, so the correction is what gets persisted.)*
- [x] 3.4 Confirm at the code level: "Remove level" is disabled for Level 1 even when 2+ levels exist, and levels 2+ remain fully editable/removable as before. *(Button `disabled={index === 0 || levels.length <= 1}`; `removeLevel` also refuses `index === 0` at the state layer. Levels 2+ untouched — same `SelectField`/remove logic as before for `index !== 0`.)*
- [x] 3.5 Confirm at the code level: when no role named "Reception" (case-insensitive) exists among the fetched roles, the page shows the blocking error message instead of rendering the form. *(`load()` sets `errorMessage` and returns before `setLevels`/`setCategoryOptions` when `receptionRole` is undefined; the page's `errorMessage ? ... : isLoading ? ... : <form>` branch renders the error state instead of the form.)*
- [x] 3.6 No backend access in this sandbox — flag as unverified whether a real organisation's role catalog actually has a role named exactly "Reception" (case variations aside) that this lookup will find, consistent with prior changes in this session. **Unverified.** If the real role is named something else (e.g. "Receptionist" or a localized name), this lookup will find nothing and every workflow form will show the blocking error until that's reconciled.
