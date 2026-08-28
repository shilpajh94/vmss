## Why

SSO (API-19, `add-sso-oidc-login`) shipped as an *additional* way in, not a
*replacement* for anyone: today `POST /auth/login` authenticates any role
(Admin, Reception, Security, Host) with a password, and the SSO callback
will happily sign into an **existing** account regardless of its role —
only brand-new, just-in-time-provisioned accounts are guaranteed never to
default to Admin. The product intent, confirmed with the user, is stricter
than what's built: **Admin signs in with a password only; every other
(staff) role signs in through SSO only.** Verifying the current
implementation against that intent surfaces two real gaps (an existing
Admin account can still complete SSO login; a tenant admin can still create
an SSO role mapping that grants Admin), not just a documentation mismatch —
so this is a behavior change, not a verification-only pass like the
sibling `verify-sso-and-full-api-suite` change.

"Two separate URLs for admin and staff" is already true today, just not
enforced: `POST /auth/login` and `GET /auth/sso/{tenantSlug}/login` are
already distinct endpoints. Per direction from the user, this change keeps
those existing paths (no renaming, no new prefixes) and makes the
separation an enforced rule instead of an unenforced convention.

## What Changes

- **BREAKING**: `POST /auth/login` rejects a caller whose account holds no
  Admin role grant (at any branch or company-wide), even with a correct
  password, with a 403 telling them to sign in via their organization's
  SSO instead. Admin accounts are unaffected.
- **BREAKING**: The SSO callback (`GET /auth/sso/callback`) rejects sign-in
  for an **existing** account that holds an Admin role grant, with a
  generic invalid-callback error (same shape as every other callback
  rejection — this must not leak *why* to an unauthenticated caller) plus a
  distinct `sso_login_rejected_admin_account` audit entry so the rejection
  is still traceable server-side. Brand-new (just-in-time) accounts already
  can never be assigned Admin by default, so this only closes the
  existing-account loophole.
- `POST /auth/sso/role-mappings` extends its existing "can't target a
  non-assignable role" guard (currently only `visitor`) to also reject a
  mapping that targets `admin`, with the same 409 the `visitor` case
  already returns — an Admin-curated mapping can no longer be created for
  a role staff are no longer allowed to reach through SSO in the first
  place.
- Any *existing* SSO role mapping already targeting `admin` (there is no
  code path that could have created one before this change other than a
  direct DB edit, since `visitor` was the only guarded name) is left as
  data for an operator to clean up — this change does not add a migration
  or backfill, since there is no evidence such a row exists in any real
  tenant.
- Documentation (`docs/features/auth.md`, `docs/features/sso_authentication.md`)
  updated to state the enforced rule plainly, replacing the current "SSO
  and password login are both always available to everyone" framing.

**Explicit assumption (flagged for review, not hidden in the fix):** the
restriction on `POST /auth/login` applies unconditionally — a staff
(non-Admin) account is rejected from password login even for a tenant that
has not finished configuring SSO yet. The user's direction ("staff users
need sso based login") was unqualified, and staff accounts created via
`sync_employee_directory` already get an unusable random password with no
self-service reset flow today, so in practice a staff account was already
never going to complete a productive password login. If this turns out to
strand a specific onboarding scenario, that's a follow-up, not something
this change should silently work around with an undocumented carve-out.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `auth`: the "JWT-Based Authentication" requirement gains a role
  restriction on `POST /auth/login` — Admin-only.
- `sso-authentication`: the callback's account-resolution behavior gains a
  rejection for an existing Admin account, and the role-mapping creation
  guard gains `admin` as a second disallowed target alongside `visitor`.
  (This capability's main spec has not been synced into `openspec/specs/`
  yet — `add-sso-oidc-login` is still an open, unarchived change. This
  delta is written against that change's pending
  `specs/sso-authentication/spec.md`, the only existing definition of this
  capability's requirements; `add-sso-oidc-login` should be archived at or
  before this change so the spec tree stays consistent.)

## Impact

- **Affected code**: `auth/router.py`/`auth/service.py` (`POST /auth/login`
  role check), `sso/service.py` (`_provision_or_resolve_user`/
  `handle_callback` existing-Admin-account check, `create_role_mapping`
  guard), `sso/tests.py`, `auth/tests.py`, both feature doc files.
- **No new endpoints, no schema/migration changes, no new dependencies.**
- **Client impact**: any staff (non-Admin) user or client currently relying
  on `POST /auth/login` must switch to the SSO flow — this is the intended
  break, not an accidental one, so it is not staged behind a deprecation
  window per `api-conventions.md` §2's normal breaking-change process;
  that process is for compatibility changes to a contract clients are
  expected to keep using, not for deliberately closing a login path a role
  is no longer permitted to use.
