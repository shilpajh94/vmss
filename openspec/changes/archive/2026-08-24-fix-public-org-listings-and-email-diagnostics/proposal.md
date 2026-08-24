## Why

Two integration-blocking issues were reported while wiring the web and
mobile clients up to this API. First, OTP request emails deliver fine
locally against Mailpit but fail on the development server with "This
delivery channel is temporarily unavailable" — the underlying SMTP error is
swallowed into a generic message with no host/port/exception detail, so the
dev-server failure can't be root-caused from logs alone. Second, every
org-structure master-data listing endpoint (branches, buildings, floors,
departments, reception desks, security gates) currently requires a bearer
token, and both clients need to render these lists (e.g. a branch/department
picker) before a visitor has authenticated — they're hitting "Invalid or
expired token" trying to call them pre-login.

## What Changes

- **BREAKING**: Remove authentication from the six org-structure *listing*
  (`GET` collection) endpoints — branches, buildings, floors, departments,
  reception desks, security gates. They become public, rate-limited, and
  unscoped by caller permission (an optional `X-Branch-ID` still narrows the
  result to one branch; omitting it returns every branch's rows for the
  tenant). Get-by-id, create, update, and delete endpoints for these
  entities are unchanged — still authenticated and permissioned as today.
- Resolve the tenant for these now-public listing endpoints the same way
  `invitations/deps.py::track_default_tenant_db` and
  `identity_verification/deps.py::default_tenant_id` already do for other
  public endpoints: via the configured default tenant slug, not a JWT claim.
- Add rate limiting (`slowapi`, IP-keyed) to the six listing endpoints,
  consistent with every other unauthenticated endpoint
  (`security-architecture.md` §2).
- Improve email-dispatch failure diagnosability in
  `identity_verification/senders.py::SmtpEmailSender.send`: log the SMTP
  host/port and the underlying exception's type/message (never credentials,
  never the OTP code) when a dispatch fails, so a dev-server-only failure
  can be root-caused from its logs instead of only reproducing locally. No
  change to the client-facing error message or status code.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `org-structure`: the branch/building/floor/department/reception-desk/
  security-gate listing endpoints no longer require authentication or a
  permission check; they resolve the tenant from the default tenant slug and
  are rate-limited instead.
- `identity-verification`: an OTP email dispatch failure now logs the SMTP
  host/port and underlying exception detail, not just a bare error string.

## Impact

- **Code**: `src/vmss_api/org_structure/router.py` (six list endpoints'
  dependencies), `src/vmss_api/org_structure/deps.py` (new public
  tenant-resolution + branch-scope dependency, mirroring
  `invitations/deps.py`), `src/vmss_api/identity_verification/senders.py`
  (`SmtpEmailSender.send`'s exception logging).
- **API contract**: the six listing endpoints no longer need (or accept as
  meaningful) a bearer token; existing authenticated callers keep working
  since a valid token is simply no longer checked. Any client-side logic
  that relied on 401/403 from these specific endpoints as an access-control
  signal must not depend on that going forward.
- **Tests**: `org_structure/tests.py` permission-denied/tenant-isolation
  cases for these six endpoints need updating — the permission-denied case
  no longer applies to listing; tenant isolation still applies (a request
  for tenant A must never surface tenant B's rows) and must be re-verified
  under the new public path.
- **No change** to org-structure's get-by-id/create/update/delete endpoints,
  or to any other capability's endpoints.
