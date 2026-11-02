# Kiosks

Admin-side management of kiosk records (tenant-scoped, one row per kiosk in the
tenant's own schema). Independent of `RegistrationDeviceKey` (see
`registrations.md`).

## Endpoints (`/api/v1/kiosks`, bearer token required)

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/kiosks` | `kiosks:manage` | 201. `name` (unique, case-insensitive among live kiosks → 409), optional `description`, `isActive` (default true). |
| GET | `/kiosks` | `kiosks:view` | Paginated. Query: `page`, `pageSize`, `status` (`active`/`inactive`), `includeHidden` (default false), `sortBy` (`name`/`created_at`), `sortOrder`. |
| GET | `/kiosks/{id}` | `kiosks:view` | Returns hidden kiosks too. |
| PUT | `/kiosks/{id}` | `kiosks:manage` | Partial update of `name`, `description`, `isActive`. |
| PATCH | `/kiosks/{id}/visibility` | `kiosks:manage` | Body `{"isHidden": bool}`. Only affects default list visibility; `isActive` is untouched. |
| DELETE | `/kiosks/{id}` | `kiosks:manage` | 204, soft delete; name becomes reusable. |

Every mutation writes an audit entry (`kiosk_created`, `kiosk_updated`,
`kiosk_hidden`, `kiosk_unhidden`, `kiosk_deleted`, entity `Kiosk`).

## Rollout

Apply tenant migration `b7c2e9a4d1f3` to each tenant schema (it also merges the
two prior tenant heads). Existing tenants pick up the new permissions and the
Admin grant via `seed_default_roles`.

## Public endpoint hardening

Some endpoints in this feature can still be called without the credential
they will eventually require. This is controlled by the
`PUBLIC_ENDPOINT_HARDENING` setting (default `false`), from the
`audit-and-harden-api-and-web` change.

- **While it is off:** these requests are served exactly as before, but the
  response carries `Deprecation: true` and a `Link` header pointing at this
  section.
- **Once it is on:** the requirement in the table below is enforced.

The target is to enable it in staging, then production, by **2026-12-31**,
once the Flutter and kiosk teams confirm their clients send the credential.
The web app already does.

| Endpoint | Strict-mode requirement |
|---|---|
| `GET /kiosks`, `GET /kiosks/{id}` | A bearer token holding `kiosks:view`, otherwise 401. In **both** modes, `includeHidden=true` is ignored for callers without `kiosks:view`. |
