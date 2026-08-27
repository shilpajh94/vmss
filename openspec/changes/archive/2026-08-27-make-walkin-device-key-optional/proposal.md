## Why

`openspec/specs/registrations/spec.md` currently requires `POST
/registrations/walk-in` to reject any request with "no device credential" as
a 401. The implementation (`registrations/deps.py::get_registration_device`)
already diverges from that: when `X-Device-Key` is absent it falls back to a
server-configured default tenant/branch instead of rejecting. That fallback
is currently documented in code only as a stopgap "known trade-off, not a
full fix" — the spec was never updated to match, so the spec and the shipped
behavior disagree, and clients (e.g. the public web portal, which has
nowhere safe to hold a device secret) get a spec-contradicting 401 whenever
they omit the header incorrectly, or a spec-contradicting success when they
correctly omit it. This change makes the no-header fallback the sanctioned,
documented default path rather than an undocumented deviation, so spec and
code agree and the behavior is no longer just a trade-off nobody signed off
on.

## What Changes

- **BREAKING** (spec-level, not code-level): redefine "missing device
  credential" from a rejected (401) case to an accepted case that resolves
  the request against the server-configured default tenant
  (`settings.default_tenant_slug`) and default branch
  (`settings.registration_default_branch_code`) — this is the existing
  `_resolve_default_device_context` fallback, formalized as intended
  behavior instead of an undocumented trade-off.
- An **invalid or unrecognized** `X-Device-Key` (header present but doesn't
  match any active device key) continues to be rejected with 401 — this
  change only affects the *absent*-header case.
- If the default tenant or default branch is missing/inactive, the request
  is still rejected with 401 (already true today) — the fallback only
  succeeds when server config actually resolves to a usable tenant/branch.
- No code changes to `registrations/deps.py::get_registration_device` are
  required — behavior already matches the new spec. This change is a spec
  correction plus removing the "known trade-off" framing from the code
  comment, since the trade-off is now an accepted, documented design
  decision rather than an open item.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `registrations`: the "Walk-in registration is authenticated by a device
  credential, not a user" requirement changes from "missing credential is
  always rejected" to "missing credential falls back to a server-configured
  default tenant/branch; only an invalid/unrecognized credential is
  rejected."

## Impact

- **Spec**: `openspec/specs/registrations/spec.md` — one requirement's
  scenarios change.
- **Code**: `src/vmss_api/registrations/deps.py` — no behavior change;
  update the `_resolve_default_device_context` docstring to drop the
  "known trade-off, not a full fix" language now that this is the
  documented, sanctioned path (tracked as a doc-only follow-up in
  `tasks.md`).
- **Security posture**: `POST /registrations/walk-in` without a device key
  remains an unauthenticated write (and file-upload) endpoint against one
  fixed branch, protected only by rate limiting — this was already true in
  practice; the change makes it an explicit, reviewed decision instead of an
  implicit one. The OTP-bound follow-up mentioned in the existing code
  comment (`security-architecture.md` §2's "fake-entry prevention") remains
  a separate, not-yet-scheduled improvement.
- **Clients**: the public web portal (which has no device secret) can now
  rely on the no-header path as documented, supported behavior rather than
  an implementation detail that could change.
