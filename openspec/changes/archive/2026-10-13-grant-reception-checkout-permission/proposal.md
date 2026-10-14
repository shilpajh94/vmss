## Why

Front office needs to check out a visitor by hand from the Visits board, for example when the visitor leaves without scanning their QR code at the exit. The endpoint already exists (`PATCH /api/v2/invitations/{id}/check-out`), but it requires `invitations:checkout`, and the standard roles grant that only to `admin` and `security`. Reception staff run the board, and today they get a 403 when they try to check someone out. The companion web change (`VMMS_WEB` → `add-manual-checkout-button`) adds the button. This change makes the call succeed for Reception.

## What Changes

- Add `invitations:checkout` to the `reception` standard role's default permission set in `auth/rbac_catalog.py::ROLE_PERMISSIONS`. New tenants get it at provisioning.
- Add a tenant migration (`alembic_tenant/`) that grants `invitations:checkout` to every existing tenant's `reception` role. The migration is idempotent, so existing tenants don't depend on an admin remembering to click "Resync permissions".
- `host` does not gain the permission. Hosts still can't check visitors out manually.
- No endpoint, schema or response change. The check-out endpoint's behaviour (only `checked_in` → `checked_out`, `409` otherwise, `Idempotency-Key` support, audit log, host push notification) stays exactly as it is.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `auth`: the standard Reception role's default permission set now includes `invitations:checkout`, and existing tenants are backfilled on upgrade.

## Impact

- **Code:** `src/vmss_api/auth/rbac_catalog.py` (one line); a new data migration in `alembic_tenant/versions/`; tests in `src/vmss_api/auth/tests.py` and `src/vmss_api/invitations/tests.py`.
- **Data:** each tenant schema gains one `role_permissions` row (reception → `invitations:checkout`). The global `permissions` catalog row already exists.
- **Security:** this widens Reception's authority. Reception can now close any `checked_in` visit at a branch where it holds the role. The permission stays branch-scoped (`authorize_branch_id_tolerant`), every check-out is still audited (`invitation_checked_out`), and `checked_out_by_user_id` records who did it.
- **Docs:** `docs/features/auth.md` (role defaults table, if listed) and `docs/features/invitations.md` (who may call check-out).
- **Clients:** none break. The web app starts showing the button to Reception via the companion change.
