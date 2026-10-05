## Why

The intended flow is: a visitor submits a request, Reception (the tenant's
default host role) sees it, and once Reception delegates it to one specific
person, **only Reception and that person** should see the request and its
details. Today, other users can still see it through two paths:

1. **Staff dashboard (`GET /invitations?relevantToMe=true`).** In the real
   workflow (step 0 = `reception`, step 1 = the `host` role, as confirmed in
   the dev tenant), the `host`-role step becomes current with no delegate as
   soon as its predecessor is approved. For example: Reception delegates
   step 0 to X, and X approves it. Another example: the gap between the
   two API calls behind the web's "Approve & Delegate" button. While that
   `host` step is unassigned, `relevantToMe` clause (c) shows the
   invitation to **every** holder of the `host` role, which is usually most
   of the company. This contradicts `DELEGATION_ONLY_ROLE_NAMES`
   (`auth/rbac_catalog.py`). That rule already stops those same people from
   acting on the step or being notified about it. Only the visibility query
   was never updated.
2. **Branch-wide listing and detail (`GET /invitations`,
   `GET /invitations/{id}`, `/admin/dashboard/*`).** These check only
   `invitations:view`, which the `host` role holds. Any host can list every
   invitation at their branch and open its full details (visitor PII,
   documents metadata, vehicle details), even if they are not involved in
   it.

## What Changes

- **BREAKING (visibility narrowing)**: `relevantToMe` clause (c) (current
  undelegated step's role-holders) no longer applies to steps whose role is
  delegation-only (`DELEGATION_ONLY_ROLE_NAMES`, i.e. `host`). An
  unassigned `host` step is visible only through the other clauses:
  Reception (e), the resolved host (a), a delegate (b), and anyone who
  already acted (d). Non-delegation-only roles (e.g. a Security or Manager
  step) keep clause (c) exactly as today.
- Add a new permission, `invitations:view-all`, meaning "see every
  invitation at this branch". Grant it to `admin` (automatically, through
  `PERMISSION_CODES`), `reception`, and `security`. Do not grant it to
  `host`.
- **BREAKING**: The branch-scoped `GET /invitations` listing (no
  `relevantToMe`) requires `invitations:view-all` instead of
  `invitations:view`. A host calling it gets 403. Hosts use
  `relevantToMe=true`, which the staff dashboard already does.
- **BREAKING**: `GET /invitations/{id}` returns the detail only if the
  caller either holds `invitations:view-all` at the invitation's branch or
  is a participant under the same (a)–(e) rule as `relevantToMe`.
  Otherwise:
  - A caller who holds `invitations:view` there gets **404**, so the
    invitation's existence is not revealed.
  - A caller with no grant at all gets **403** (unchanged).
  As a side effect, a delegate who holds no `invitations:view` grant can
  now open the invitation they were assigned. Today they get 403.
- `/admin/dashboard/overview`, `/checkins`, and `/search` switch their gate
  from `invitations:view` to `invitations:view-all`, so a host cannot query
  branch-wide visitor names or counts through them.
- Add a tenant data migration that grants `invitations:view-all` to every
  existing role that currently holds `invitations:view`, except `host`.
  Existing tenants and custom roles (e.g. a "manager" role) keep their
  current branch-wide access without manual re-granting.
- No change to who can **act** on a step (`approvals` capability), to how a
  delegate is chosen, or to the web portal. Admin and Security boards keep
  their branch-wide views. The staff dashboard already calls
  `relevantToMe=true`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`:
  - "Caller Lists Invitations Relevant to Themselves via relevantToMe":
    clause (c) excludes delegation-only roles.
  - "Employee Lists Invitations at Their Authorized Branches": now requires
    `invitations:view-all`.
  - New requirement: participant-scoped visibility for
    `GET /invitations/{id}`.
- `dashboard`: new requirement that the dashboard endpoints are gated on
  `invitations:view-all`.
- `auth`: new requirement for the `invitations:view-all` catalog permission,
  its default role grants, and the backfill for existing roles.

## Impact

- `src/vmss_api/invitations/repository.py`:
  - `_relevant_to_me_filter` clause (c) excludes delegation-only roles.
  - New `is_relevant_to(invitation_id, user_id, default_host_role_id)` that
    reuses the same filter for a single-row check.
- `src/vmss_api/invitations/router.py`:
  - `list_invitations` uses `invitations:view-all` on the branch path.
  - `get_invitation_detail` uses the new view-all-or-participant check.
- `src/vmss_api/invitations/service.py`: a thin wrapper for the participant
  check.
- `src/vmss_api/dashboard/router.py`: three permission strings change.
- `src/vmss_api/auth/rbac_catalog.py`: new permission code and role grants.
- `alembic_tenant/versions/<new>_grant_invitations_view_all.py`: backfill
  migration, `down_revision = c3d5e7f9a1b2`.
- Tests: `invitations/tests.py`, `dashboard` tests, `auth` catalog tests.
- `docs/features/invitations.md` and `docs/features/dashboard.md`:
  permission notes.
- **Ordering with an open change:** `harden-approval-gate-and-narrow-delegate-visibility`
  is implemented in code but not yet archived. Its `invitations` delta
  modifies the same `relevantToMe` requirement. This change's delta is
  written against that post-harden text, so archive `harden-...` first.
- **Deploy:** existing tenants need `scripts/upgrade_all_tenants.py`, which
  runs the migration plus `seed_default_roles`. Until it runs, Reception
  and Security get 403 on the branch listing. The prestart drift check
  warns about the lagging tenant.
- API contract: same endpoints and shapes. The permission and status-code
  changes are listed above. Clients are the admin board (admin, unaffected)
  and the staff dashboard (already uses `relevantToMe`).
