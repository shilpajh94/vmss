## Context

`invitations:checkout` already exists in the global `permissions` catalog and gates `PATCH /api/v2/invitations/{id}/check-out` through `authorize_branch_id_tolerant`. `ROLE_PERMISSIONS` in `auth/rbac_catalog.py` currently grants it only to `admin` (all codes) and `security`. `seed_default_roles` union-merges these defaults at provisioning time and on `POST /auth/roles/resync-permissions`, so a catalog edit alone covers new tenants and any tenant whose admin runs the resync. Nothing else touches existing tenants. The precedent for pushing a grant automatically is `alembic_tenant/versions/d4e6f8a0b2c3_grant_invitations_view_all.py`.

The companion change, `VMMS_WEB` → `add-manual-checkout-button`, adds the UI that makes Reception call this endpoint.

## Goals / Non-Goals

**Goals:**
- Reception can call the existing check-out endpoint at branches where it holds the role, in new and existing tenants, without manual admin action.

**Non-Goals:**
- No change to the check-out endpoint, its state machine or its response shape.
- No permission for `host`. A host checking their own visitor out is a separate product decision.
- No exposure of the caller's permission set to the web app. The web change gates the button by role name (`isAdmin`/`isReception`), as it does for other Reception-only actions.

## Decisions

**1. Edit the catalog *and* add a tenant data migration, rather than relying on the resync button.**
`seed_default_roles` only runs at provisioning or when an admin clicks "Resync permissions". Shipping the web button while existing tenants' Reception roles still lack the grant would show every receptionist a button that returns 403 until someone remembers the resync. A tenant migration runs as part of the normal "upgrade all tenants" path and removes that gap.
*Alternative considered:* catalog edit plus a release note telling admins to resync. Rejected because it is error-prone and invisible to the people who would hit the 403.

**2. The migration grants only to the standard role matched by `lower(name) = 'reception'`.**
This mirrors how `d4e6f8a0b2c3` identifies `host`. Custom roles are left alone. Unlike `view-all`, this is not a split of an existing permission, so no custom role loses access it had before. Admins can still grant the permission to custom roles from the Roles page.
*Alternative considered:* grant to every role holding `invitations:approve` or `invitations:view-all`. Rejected because it would also give Host-like custom roles authority to close visits, which goes beyond what was asked.

**3. Use `INSERT … SELECT … ON CONFLICT DO NOTHING` against the existing catalog row.**
This is idempotent, and it is a no-op for any tenant whose admin already resynced after the catalog edit. Downgrade deletes only the `reception` → `invitations:checkout` grant in that schema. It never touches the global catalog row, which `admin`/`security` and other tenants still reference.

**4. Chain the migration off the current single tenant head (`a7c3e9f1b2d4`).**
Run `alembic -c alembic_tenant.ini heads` immediately before opening the PR. If another branch has added a tenant revision in the meantime, rebase `down_revision` rather than leaving two heads.

## Risks / Trade-offs

- [Reception gains authority to close any visit at its branch] → The scope is branch-limited. Every call is audited (`invitation_checked_out`, actor id) and stamped with `checked_out_by_user_id`, so misuse is traceable.
- [Downgrade removes a grant an admin may have added manually before this release] → This is acceptable and matches `d4e6f8a0b2c3`'s downgrade semantics. Downgrades are an ops escape hatch, not a routine path.
- [Two tenant heads if another tenant migration merges first] → Decision 4's pre-PR `heads` check.

## Migration Plan

1. Deploy the API: `alembic upgrade head` (global, no-op), then upgrade every tenant schema. The new revision grants Reception the permission.
2. Deploy the web change after this. If the web change ships first, Reception sees the button and gets a 403 toast until step 1 lands. That is harmless, but avoid it.
3. Rollback: downgrade the tenant revision. The web button would then 403 for Reception again, so roll back the web change as well.
