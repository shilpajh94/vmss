## Why

The frontend team reports `POST /registrations/walk-in` returning 401
`"Invalid device credential"`, plus `GET /visit-info/departments`,
`GET /hosts/search`, and `GET /visit-info/options` behaving as if a device
key is mandatory — even though none of these endpoints carry a bearer
token, so per this API's own convention (`security-architecture.md` §2)
none of them should require a client-held credential to function at all.

Investigation traced this to two distinct, narrower problems rather than a
missing "make it optional" fix:

1. Device-key optionality is **already implemented and already spec'd**
   (`openspec/specs/registrations/spec.md` "Missing or invalid device
   credential" — merged today via
   `openspec/changes/archive/2026-08-27-make-walkin-device-key-optional/`,
   and shared into all three `visit-info` lookup endpoints via
   `registrations/deps.py::get_registration_device`). But when the caller
   omits `X-Device-Key`, the fallback path resolves a server-configured
   default tenant/branch (`settings.default_tenant_slug` /
   `settings.registration_default_branch_code`) — and if that
   configuration is missing or unresolved (as it is in `vmss-dev` today,
   see Impact), the request is rejected with the exact same
   `"Invalid device credential"` 401 a genuinely bad device key would
   produce, at only `WARNING` level. From the frontend's side this is
   indistinguishable from "the device key I'm not sending is somehow
   required" — which is exactly what was reported, even though no code
   path is actually enforcing a mandatory key.
2. `GET /hosts/search` is a real case of an unnecessarily mandatory
   parameter: its `query` param has no default, so calling it without one
   is rejected with a 422 before any device-key logic even runs. This one
   needs an actual behavior change, not just a diagnosis.

## What Changes

- **`registrations`**: split the single `"Invalid device credential"` 401
  outcome into two distinguishable cases:
  - The caller sent an `X-Device-Key` that doesn't match any active,
    provisioned device (or resolves to an inactive tenant/branch) — client
    error, unchanged 401 + `"Invalid device credential"` message, logged at
    `WARNING` (unchanged).
  - The caller sent no `X-Device-Key` and the server-configured default
    tenant or default branch is missing/inactive — this is a **server
    misconfiguration**, not a bad client credential. Still 401 (no
    registration should be silently created against an unresolved branch),
    but with a distinct message (`"Registration service is not configured
    for this environment"`) and logged at `ERROR` (not `WARNING`), per
    `logging-observability.md` §3's "needs a human to look" bar — a missing
    default tenant/branch should page someone, not sit in a log stream at a
    level nobody alerts on.
  - No change to the already-correct behavior of falling back to the
    default tenant/branch when the header is simply absent and that
    default *is* configured and active.
- **`visit-info-lookup`** (`GET /hosts/search`): make `query` optional.
  When omitted or blank, return up to `limit` active employees ordered
  alphabetically by name (the existing "browsable" shape, not an error) —
  the same response contract as a matched search, just unfiltered. The
  existing 2-character minimum validation still applies when a `query` is
  supplied.
- **Test coverage**: add the missing regression tests (identified as a gap
  during investigation — `visit_info/tests.py` currently only exercises
  these three endpoints with a valid device key) proving `X-Device-Key` is
  optional on `GET /visit-info/departments`, `GET /hosts/search`, and
  `GET /visit-info/options`, mirroring the coverage `registrations/tests.py`
  already has for walk-in. This directly closes the frontend team's
  suggestions #1 and #3, which this investigation found were already true
  in code but unverified by tests and apparently unconfirmed in the
  environment they tested against.
- **Docs**: update `docs/features/registrations.md` and
  `docs/features/visit-info-lookup.md` (or wherever visit-info lookup
  endpoints are documented once `visit-info-lookup-api` is archived) to
  state explicitly, for API consumers, that `X-Device-Key` is optional on
  all four endpoints and what happens when it's omitted.
- **Not a code change, flagged as an action item**: `vmss-dev`'s `.env`
  currently ships unresolved placeholder values —
  `TENANT_DEFAULT_SLUG=__TENANT_DEFAULT_SLUG__` and
  `REGISTRATION_DEFAULT_BRANCH_CODE=__REGISTRATION_DEFAULT_BRANCH_CODE__`
  (confirmed in this repo's local `.env`, `.env.example` carries the same
  placeholders by design). Whoever manages the `vmss-dev` environment needs
  to set these to a real tenant slug and branch code — this is the actual
  trigger for the reported walk-in 401, and no code change in this repo can
  fix a per-environment `.env` value.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `registrations`: "Missing or invalid device credential" behavior now
  distinguishes a bad/absent-with-no-fallback device credential (client
  error) from an unconfigured server-side default tenant/branch (server
  misconfiguration), with different response messages and log levels.
- `visit-info-lookup`: "Host Search Validates Query Length and Caps Result
  Count" changes so `query` is optional — an omitted/blank query returns a
  browsable default list instead of a validation error. (This capability's
  base spec has not yet been archived from `openspec/changes/
  visit-info-lookup-api/specs/visit-info-lookup/spec.md` into
  `openspec/specs/`; this delta is written against that pending spec since
  the behavior it describes is already implemented and live.)

## Impact

- **Code**: `src/vmss_api/registrations/deps.py` (error message/log-level
  split), `src/vmss_api/visit_info/router.py` and
  `src/vmss_api/visit_info/service.py` (optional `query` on
  `search_hosts`), `src/vmss_api/registrations/tests.py` /
  `src/vmss_api/visit_info/tests.py` (new coverage).
- **Docs**: `docs/features/registrations.md`, visit-info-lookup feature
  doc.
- **No API contract break**: response envelope shape, status codes, and
  existing required/optional fields are unchanged except `query` becoming
  optional on `GET /hosts/search` (a loosening, not a breaking change per
  `api-conventions.md` §2) and the 401 message text differing by failure
  cause (message text isn't a versioned contract field).
- **Environment**: `vmss-dev` `.env` needs `TENANT_DEFAULT_SLUG` /
  `REGISTRATION_DEFAULT_BRANCH_CODE` set to real values — outside this
  change's code, flagged for the environment owner.
