## Why

`complete-api-test-coverage` (archived 2026-08-21) closed every per-endpoint
scenario gap `testing-standards.md` §2 requires, but every one of those tests
is scenario-isolated: a test's fixtures are built directly via
`polyfactory` factories or root `conftest.py` fixtures inserted straight into
the DB, not by actually calling the prior API in the chain and carrying its
real response (a token, a created id) into the next call. There is currently
no test that proves the APIs actually compose into a working end-to-end
journey the way a real caller — an admin setting up a tenant, or a visitor
being registered — would exercise them in sequence. A per-endpoint contract
test passing does not prove the sequence works: a token-shape change, a
field renamed between what one endpoint returns and what the next expects, or
a permission wired to the wrong role would slip through isolated tests but
break a real user in one HTTP call.

This product has two structurally distinct caller types with no shared step
between them (authenticated staff/admin users vs. unauthenticated
visitor-facing public endpoints), so this change builds two separate chained
test suites rather than forcing one flow to cover both.

## What Changes

- Add a **staff/admin workflow test** that chains real HTTP calls, each
  carrying forward the real response from the previous call (a token, a
  created id — never a shortcut fixture), through: platform tenant
  provisioning → tenant-admin login → create a second staff user and assign
  a branch role → build the org structure chain (company → branch →
  building → floor → department → reception desk → security gate) →
  configure a visitor category and approval-workflow rule → list endpoints
  reflecting everything just created → update and delete a couple of the
  created entities → the cross-branch reports rollup reflecting the final
  state. Every step after tenant provisioning uses the token/ids the
  previous step actually returned.
- Add a **visitor workflow test** that chains: an authenticated staff member
  creates an invitation for a visitor → the visitor (unauthenticated)
  completes identity verification (OTP request + verify) → the visitor
  tracks their own invitation status via the public tracking endpoint. A
  second variant covers the walk-in path (device-key-authenticated
  registration → public tracking) instead of the staff-created invitation.
- Both suites assert the *shape* of what each step hands to the next (e.g.
  the login response actually contains a bearer token in the field the next
  request's `Authorization` header expects; the invitation-create response's
  `trackingId` is actually what the tracking endpoint accepts) — not just
  that each individual call independently returns 2xx.
- No production code is expected to change. If a chained call fails in a way
  an isolated test didn't catch (a real integration bug), that's reported and
  fixed the same way `complete-api-test-coverage` handled bugs it found —
  this change does not pre-commit to a fix before knowing whether one is
  needed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this adds test coverage of how already-specified endpoints compose
together; it does not change what any single endpoint is specified to do. If
a chained test surfaces a real behavior gap between two endpoints' specs, that
is a new finding for a separate change, not a silent spec edit here. This
change sets `skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **New test files**: a root-level `tests/` module (or per the project's
  existing "cross-feature tests live in root `tests/`" convention already
  used by `tests/test_api_documentation.py`) — exact filename(s) decided in
  design.md — for the two chained workflow suites. These are genuinely
  cross-feature, so they don't belong inside any single feature's
  `tests.py`.
- **No changes to any feature's existing `tests.py`, `router.py`,
  `service.py`, or `repository.py`** unless a chained test uncovers a real
  bug, in which case the fix is scoped exactly like a bug found during
  `complete-api-test-coverage` was (see that change's `summary.md` for the
  precedent).
- **No dependency, schema, or migration changes.**
- **No breaking changes.**
