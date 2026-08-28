## Context

See `proposal.md` — Why for motivation. The two entry points already have
separate URLs (`POST /auth/login` vs. `GET /auth/sso/{tenantSlug}/login` →
`GET /auth/sso/callback` → `POST /auth/sso/exchange`), per the user's
explicit choice not to rename anything. What's missing is enforcement:

- `auth/service.py::authenticate_user` checks password validity only —
  never the caller's role.
- `sso/service.py::_provision_or_resolve_user` only guards role assignment
  for **new** accounts (default `host`, mapping table can't target
  `visitor`). An **existing** account found by email is returned as-is,
  with whatever role(s) it already holds — including Admin.
- `sso/service.py::create_role_mapping` guards `visitor` as a mapping
  target but not `admin`.

A `User`'s role is not a single column — it's derived from
`UserBranchRole` rows (company-wide, `branch_id IS NULL`, or scoped to a
specific branch), each pointing at a `Role`. "Holds the Admin role" means
"has at least one non-revoked `UserBranchRole` whose `role.name == "admin"`
(case-insensitive, matching how `STANDARD_ROLE_NAMES` is compared
elsewhere)" — regardless of which branch it's scoped at, since Admin is
normally granted company-wide.

## Goals / Non-Goals

**Goals:**
- Password login succeeds only for Admin-role accounts.
- SSO login (both fresh JIT provisioning and an existing-account match)
  never signs into an Admin-role account.
- Both rejections are the appropriate generic shape for their endpoint
  (password login's existing 401-style non-disclosure pattern for the
  credential check itself, actually 403 since credentials *were* valid;
  SSO callback's existing generic-error pattern) and remain traceable in
  the audit log.

**Non-Goals:**
- No new endpoints, no URL renaming (user's explicit direction).
- No change to how Admin itself is granted (`POST /auth/users/{id}/branch-roles`,
  gated by `users:manage`) — this change only gates *login method*, not
  role assignment.
- No handling for a hypothetical pre-existing `SsoRoleMapping` row already
  targeting `admin` — proposal.md's Impact section already covers why
  (no code path could have created one; a direct DB edit is an operator
  problem, not something this change migrates around).
- No change to the "an unreachable IdP does not lock out password login"
  guarantee for Admin — that requirement (`sso-authentication` capability)
  is about Admin's own login continuing to work, which is unaffected here.

## Decisions

**1. Where the `POST /auth/login` role check lives.**
In `auth/service.py::authenticate_user`, immediately after the existing
password check and before returning `(user, tenant)` — the router
(`auth/router.py::login`) has no other place that sees the resolved `User`
with its `branch_roles` loaded. Reuses the same `invalid_credentials`-style
rejection pattern already in that function (single exit path, no
information leakage about *which* check failed) but as a distinct
exception/message, since this isn't a credential problem — the user is
told to use SSO, not to check their password. Alternative considered:
checking role in the router after `authenticate_user` returns — rejected
because `authenticate_user` already loads `user.branch_roles` (via `User`'s
`lazy="selectin"` relationship) and is the one place that already knows
both the user and which check is failing; splitting it into the router
would duplicate the "what counts as Admin" logic that the SSO side also
needs (see Decision 2), so it belongs in one shared helper instead.

**2. A shared `has_admin_role(user: User) -> bool` helper.**
Both `auth/service.py` (password-login gate) and `sso/service.py`
(callback's existing-account gate) need the identical "does this user hold
Admin" check. Defined once in `auth/service.py` (the module that owns
`User`/`Role`/`UserBranchRole`) and imported by `sso/service.py` — mirrors
the existing direction of that dependency (`sso/service.py` already imports
`vmss_api.auth.service as auth_service` for `create_user`), so this adds no
new import edge.

**3. `POST /auth/login`'s rejection is 403, not 401.**
401 is reserved for "credentials are missing/invalid" (`security-architecture.md`
§1's Standardized Security Responses). Here the password *was* correct —
the caller is authenticated but using a login method their role isn't
permitted to use, which is exactly what 403 means in this codebase
(authenticated-but-insufficient-permission). The response message is
generic enough ("Sign in via your organization's SSO login") that it does
not confirm the password was correct, only that this login method isn't
available to this account — an acceptable, minor information disclosure
consistent with how SSO already tells an unauthenticated caller which
tenant slugs exist (`start_login`'s 404 vs. 409 behavior is already
tenant-existence-revealing by design).

**4. SSO callback's Admin rejection reuses `InvalidSsoCallbackError`, with
a distinct audit action instead of a distinct HTTP response.**
Every other callback failure (bad state, bad token, missing email) returns
the same generic `InvalidSsoCallbackError` shape specifically so an
unauthenticated caller can't distinguish failure reasons. An Admin-account
rejection follows the same rule — the HTTP response looks identical to any
other rejected callback — but the audit log gets its own action name
(`sso_login_rejected_admin_account`) instead of the generic
`sso_login_failed`, matching this codebase's existing pattern of "generic
to the caller, specific in the audit trail" (e.g. `sso_login_failed` vs.
`sso_account_created` are already both written from the same function for
different outcomes). Written synchronously via `record_audit_log`
(`await`ed directly), not `background_tasks.add_task`, for the same reason
`handle_callback`'s existing failure paths already do this: a route that
raises an `HTTPException` never gets its `BackgroundTasks` attached to the
error response (see the existing comment in `sso/service.py`).

**5. `create_role_mapping`'s new `admin` guard sits next to the existing
`visitor` guard, same 409.**
Both are "this role must never be reachable via a curated SSO mapping"
checks; no reason to give `admin` a different status code or message
shape than `visitor` already uses.

## Risks / Trade-offs

- **[Risk] `sso-authentication`'s main spec isn't archived yet.** This
  change's spec delta for that capability is written against
  `add-sso-oidc-login`'s still-open delta, not a main spec under
  `openspec/specs/`. → **Mitigation**: flagged in `proposal.md`'s Impact
  section; `add-sso-oidc-login` (and ideally `verify-sso-and-full-api-suite`,
  which touches the same files) should archive at or before this change so
  `openspec/specs/sso-authentication/spec.md` exists with the base
  requirements this change's delta assumes, before this change's own delta
  is applied on top.
- **[Risk] An existing Admin account that is *also* staff-mapped** (a
  tenant grants one person both an Admin `UserBranchRole` and, say, a
  Security one at a different branch) **is now fully blocked from SSO**,
  even for the branches where they only hold the Security grant. →
  **Mitigation**: accepted as correct per the user's direction — "holds
  Admin" is checked account-wide, not per-branch, because password login
  (the only path left for that account) is also account-wide, not
  branch-scoped; there is no partial state where an SSO login could
  legitimately grant only the non-Admin portion of that account's access.
- **[Risk] Operational lockout during tenant onboarding** if SSO isn't
  configured yet and a staff account somehow has a usable password
  (created directly via `POST /auth/users` rather than directory sync). →
  Already called out as an explicit, unresolved-by-design assumption in
  `proposal.md`; not mitigated further here since the user's direction was
  unconditional and no evidence of this actually happening was found.

## Migration Plan

No data migration. Deploy is a single atomic code change (service-layer
checks + one guard clause); no feature flag, since both gates are
correctness fixes for an already-stated business rule, not a gradual
rollout — a partial rollout would mean some Admin accounts can SSO and
others can't, which is strictly worse than shipping the whole gate at
once. Rollback is a plain revert if needed; no rows are altered.
