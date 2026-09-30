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
