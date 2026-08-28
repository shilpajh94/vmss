## Why

The user asked whether the previously-shipped
`harden-referential-integrity-and-rbac-gates` change covers a reported
"hardcoded branch MAIN" walk-in failure. It does not — that change closed a
different, if structurally similar, hole. `POST /registrations/walk-in`
resolves tenant/branch two ways: from a provisioned `RegistrationDeviceKey`
(the case the prior change protects), or, when no `X-Device-Key` header is
sent at all, from a single server-configured default branch code
(`settings.registration_default_branch_code`, defaulting to `"MAIN"` —
`core/config.py`, `.env`, and `scripts/seed_dev_data.py` all agree on this
value). Nothing stops an admin from soft-deleting or renaming the `code` of
whichever `Branch` currently matches that configured default: the prior
change's guard only checks for active org-chart children or an active
`RegistrationDeviceKey`, neither of which exists for a branch that only
ever serves the no-device-key fallback. Once that branch's code no longer
resolves, every future no-device-key walk-in request 401s with "Registration
service is not configured for this environment" — already-correct,
already-spec'd behavior for the *degenerate state*
(`openspec/specs/registrations/spec.md`'s "Unconfigured default
tenant/branch is reported and logged as a server misconfiguration"), but
nothing today prevents an admin from creating that degenerate state via a
completely ordinary branch delete or rename.

## What Changes

- **Block deleting the branch that matches the configured walk-in default
  code.** `org_structure/service.py::delete_branch` gains a third guard
  check, alongside the existing active-children and active-device-key
  checks: if `branch.code == settings.registration_default_branch_code`,
  reject with 409 instead of soft-deleting.
- **Renaming a branch's `code` turned out to already be unreachable —
  confirmed during implementation, not assumed at proposal time.**
  `BranchUpdate` (`org_structure/schemas.py`) has no `code` field at all;
  Pydantic silently drops an unknown `code` key from a `PUT /branches/{id}`
  body rather than validating or applying it. There is no path through
  `update_branch` that can ever change a branch's `code`, so no second
  guard is needed there — the plan to add one (recorded in this proposal's
  first draft) was dropped once this was verified against the actual
  schema, per the project's "don't guard against scenarios that can't
  happen" convention. `delete_branch`'s guard is the complete fix.
- The delete guard doesn't fire for a branch whose code doesn't match the
  configured default — every other branch's delete behavior is completely
  unchanged.
- If an operator genuinely needs to retire "MAIN" as the walk-in default,
  the correct sequence becomes: update `REGISTRATION_DEFAULT_BRANCH_CODE`
  to point at a different branch's code first (a config change/redeploy),
  then delete the old one — the same "change the dependency first, then
  remove what it depended on" shape the prior change already established
  for active children/device keys.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `org-structure`: adds a referential-integrity requirement that a branch
  matching the configured walk-in default branch code cannot be deleted,
  extending the same posture `harden-referential-integrity-and-rbac-gates`
  established for active children/device keys (a new, independent
  requirement — not a modification of that change's own still-unarchived
  delta).

## Impact

- **Code**: `src/vmss_api/org_structure/service.py` (`delete_branch` only —
  `update_branch` needed no change, see "What Changes" above).
- **Tests**: new cases in `org_structure/tests.py` — deleting the
  configured-default-code branch is rejected; deleting any other branch is
  unaffected; a `code` field sent to `update_branch` is confirmed to be a
  no-op (documenting why no second guard is needed there).
- **Compatibility**: this closes a previously-silent misconfiguration path
  (delete succeeded, 204, with no warning) into a 409 — a new restriction,
  not a change to any documented success/error contract for a request that
  has a legitimate reason to succeed today. No existing test's behavior
  changes unless it happens to delete a branch whose code is literally the
  configured default (four do — the shared `branch` fixture's code is
  `"MAIN"` in `conftest.py`, which *is* the default; see `design.md` for
  how those four tests stay green).
