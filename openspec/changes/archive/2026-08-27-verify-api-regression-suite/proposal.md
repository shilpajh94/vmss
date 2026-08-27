## Why

`fix-visit-info-lookup-access` just changed shared, widely-reused code:
`registrations/deps.py::get_registration_device` is the device-credential
resolver every `visit_info` endpoint and `POST /registrations/walk-in`
depend on, and `auth/repository.py::search_active_by_name_or_email` backs
host search. The apply session verified those touched areas directly (the
full `pytest` suite plus a live-workflow simulation of the four reported
endpoints), but the user has now asked for a broader pass: confirm the full
test suite is green from a clean run and that every feature's API surface —
not just the four endpoints named in the original bug report — still
behaves correctly, so a change to shared auth/tenancy-adjacent code hasn't
silently regressed something outside its own feature's test file.

## What Changes

- No source code changes. This is a verification pass: run the full
  `pytest` suite from a clean state, then exercise each feature's endpoints
  through the real ASGI app (the same "as the frontend would call them"
  approach used in the prior apply session — real HTTP-shaped
  request/response objects, real Postgres, no mocks) to confirm the
  request/response contract each feature's own tests already assert still
  holds after the shared-dependency change.
- If any test fails or any endpoint misbehaves during this pass, fix the
  regression (scoped to the smallest correct change) and re-verify — the
  proposal's "what changes" in that case is whatever the failure turns out
  to require, decided at the time based on what's actually broken rather
  than guessed now.
- Produces no new or modified capability behavior when nothing is broken;
  `skip_specs: true` is set accordingly. If a genuine behavior regression
  is found and fixed, the fix itself is scoped to restoring the already-
  documented spec (i.e., existing `openspec/specs/**` requirements), not
  introducing new behavior — so no spec delta is expected there either.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — verification only; `skip_specs: true` set in `.openspec.yaml`. Any
fix made in response to a discovered regression restores existing,
already-specified behavior rather than changing a requirement.)

## Impact

- **Code**: none planned. Any fix arising from a discovered failure is
  scoped to the specific broken file(s) at that time.
- **Systems**: local DDEV Postgres/Redis only — no staging/prod impact.
- **Scope of verification**: every feature package under `src/vmss_api/`
  (`auth`, `identity_verification`, `invitations`, `org_structure`,
  `platform`, `registrations`, `reports`, `sso`, `tenant`, `visit_info`,
  `visitors`) via its own `pytest` coverage, plus a targeted live-request
  pass over the endpoints most exposed to the recent shared-dependency
  change (`registrations`, `visit_info`, and anything else authenticating
  through `get_registration_device`/`get_registration_tenant_db`).
