## Why

`GET /api/v1/visit-info/departments` on `vmss-dev` returns 401 `"Registration
service is not configured for this environment"`. Root-causing it against
`registrations/deps.py::_resolve_default_device_context` (which `visit_info`
reuses) shows the endpoint is behaving exactly as
`openspec/specs/registrations/spec.md`'s "Unconfigured default tenant/branch"
scenario already specifies: with no `X-Device-Key` header (the case for the
web portal), the server falls back to a single configured default tenant
(`TENANT_DEFAULT_SLUG`) and branch (`REGISTRATION_DEFAULT_BRANCH_CODE`); on
`vmss-dev` that tenant/branch pair does not currently resolve to an active
row, which is a deployment-provisioning gap on that environment, not a code
defect in this endpoint.

Auditing every other implemented API for the same class of risk — so this
class of failure doesn't reappear elsewhere during web/app integration —
surfaced that three other public, unauthenticated endpoints
(`identity_verification`'s OTP request/verify, and
`GET /invitations/track`) independently re-implement the identical "resolve
`settings.default_tenant_slug`" logic `registrations` already has, but
neither logs at `ERROR` nor distinguishes "no such tenant" from "tenant
inactive" the way `registrations/deps.py` and its spec require —
`logging-observability.md` §3 calls a server misconfiguration an `ERROR`-bar
event precisely so an operator finds it without reproducing the failure
live, and today two of these four call sites give an operator nothing to
find. Separately, `/health/ready` (`main.py`) verifies Postgres and Redis
connectivity but never verifies the configured default tenant/branch
actually resolve, so a deployment in this exact misconfigured state reports
"ready" right up until a real caller hits it — which is what happened here.

## What Changes

- **Consolidate the four independent "resolve `settings.default_tenant_slug`"
  implementations** (`registrations/deps.py::_resolve_default_device_context`,
  `identity_verification/deps.py::default_tenant_id`,
  `invitations/deps.py::track_default_tenant_db`, and `visit_info`'s reuse of
  the first) into one shared helper in `core/`, so the logging/error-message
  behavior can't drift between call sites the way it already has.
- **Fix: `identity_verification`'s OTP request/verify and
  `GET /invitations/track` now log at `ERROR` and distinguish "tenant not
  found" from "tenant inactive"** when the default tenant fails to resolve,
  matching the behavior `registrations/deps.py` already has and
  `logging-observability.md` §3 requires for a server-side misconfiguration.
  Their client-facing responses keep their existing status code/message
  shape for each feature (no client-visible contract change) — only the
  server-side log gains the same diagnosability `registrations` already has.
- **Add a default-tenant/branch resolution check to `GET /health/ready`**,
  so a deployment whose configured default tenant or walk-in default branch
  doesn't resolve to an active row is reported unready instead of healthy,
  catching this exact misconfiguration class before a real caller does.
- **Document the required provisioning step** for `TENANT_DEFAULT_SLUG` /
  `REGISTRATION_DEFAULT_BRANCH_CODE` in `docs/features/configuration.md`,
  so standing up a new environment (as `vmss-dev` needed) has a checked step
  for this instead of relying on a live request to discover the gap.
- No change to any endpoint's existing success-path contract, and no change
  to the deliberate, already-spec'd "unauthenticated fallback with no
  device credential" trade-off itself (`security-architecture.md` §2,
  `registrations/spec.md`) — this hardens observability and detection of the
  misconfigured state, not the state's existence.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `environment-configuration`: adds a requirement that readiness reporting
  verifies the configured default tenant and default walk-in branch resolve
  to active rows, not just that the database/cache are reachable.
- `identity-verification`: adds a requirement that default-tenant
  resolution failure for the OTP request/verify endpoints is logged at
  `ERROR` with a not-found/inactive distinction, consistent with
  `registrations`' existing requirement of the same shape.
- `invitations`: adds the equivalent requirement for
  `GET /invitations/track`'s default-tenant resolution.

## Impact

- **Code**: a new shared resolver in `src/vmss_api/core/` (exact module
  named in `design.md`); `identity_verification/deps.py`,
  `invitations/deps.py`, and `registrations/deps.py` updated to call it
  instead of their own copies; `main.py`'s `/health/ready`.
- **Docs**: `docs/features/configuration.md` gains the provisioning
  checklist entry; `docs/features/identity_verification.md` and
  `docs/features/invitations.md` updated to describe the new ERROR-log
  behavior.
- **Tests**: `identity_verification/tests.py`,
  `invitations/tests.py`, and a `main.py`/health test gain regression
  coverage for the newly-consistent logging and the readiness check;
  existing `registrations/tests.py` coverage is the reference behavior the
  others are brought in line with.
- **Compatibility**: no change to any client-visible success response.
  `/health/ready` gains a new failure mode (503) for a misconfiguration that
  previously reported "ready" — a deployment that is correctly configured
  today sees no change in that endpoint's response.
- **Operational**: this does not fix `vmss-dev`'s actual misconfiguration —
  that requires provisioning/activating a tenant matching `TENANT_DEFAULT_SLUG`
  and a branch matching `REGISTRATION_DEFAULT_BRANCH_CODE` in that
  environment's database (or correcting those two settings to match what is
  already provisioned there), which is an environment/ops action this change
  does not perform.
