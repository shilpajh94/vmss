## Why

`POST /registrations/walk-in` without an `X-Device-Key` returns 401
`"Registration service is not configured for this environment"` whenever the
server-configured default tenant or default branch can't be resolved. The
current `ERROR` log (`registration_default_tenant_unconfigured` /
`registration_default_branch_unconfigured`, in `registrations/deps.py`)
already tells an operator *which* of the two (tenant or branch) is the
problem, but not *why*: `tenant is None or not tenant.is_active` and
`branch is None or not branch.is_active` are each collapsed into one log
event, so "no such tenant row exists" and "the tenant row exists but is
deactivated" are indistinguishable from the log alone. An operator hitting
this has to go read `deps.py` to know whether the fix is provisioning a
missing row or re-activating an existing one.

## What Changes

- Add a `reason` field (`"not_found"` or `"inactive"`) to the
  `registration_default_tenant_unconfigured` and
  `registration_default_branch_unconfigured` `ERROR` log events in
  `_resolve_default_device_context`, so the two failure causes are
  distinguishable without reading source.
- No change to the 401 response body: the client-facing detail stays the
  generic `"Registration service is not configured for this environment"` —
  the existing spec requirement (`registrations` capability) already
  intentionally keeps that message free of internal detail, and this change
  doesn't touch that behavior.
- No change to the invalid-device-credential path (`WARNING`-level, client-side
  anomaly) — this is scoped to the server-misconfiguration path only.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `registrations`: the "Unconfigured default tenant/branch is reported and
  logged as a server misconfiguration" scenario gains a requirement that the
  `ERROR` log distinguishes "row does not exist" from "row exists but
  inactive" for both the default tenant and default branch cases.

## Impact

- `src/vmss_api/registrations/deps.py` — `_resolve_default_device_context`,
  `_reject_unconfigured_default` (add a `reason` kwarg/field).
- No API contract change (response body, status code, and headers are
  unchanged) — logging only.
- No migration, no config/settings change.
