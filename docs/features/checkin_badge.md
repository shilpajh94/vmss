# Check-in badge print flow

Reception finds a visit, confirms the visitor's ID, and prints a PDF badge whose
QR was generated at reception, is valid for that one day, and is revoked when
the badge is reprinted. The badge QR then drives checkout and same-day re-entry.
Everything lives in `src/vmss_api/checkin/` and ships **dark**: with the flag off
no existing behavior changes. A "visit" is an `Invitation` row, so `{visit_id}`
is an invitation id. The older PNG badge (`POST /invitations/{id}/badge`) is
untouched.

## Enabling it

Two switches, both must be on, otherwise every route below returns `404`:

1. `BADGE_PRINT_FLOW_ENABLED=true` (deploy-level; default `false`).
2. The tenant's toggle: `PATCH /api/v1/tenants/me/settings` with
   `{"badgePrintFlowEnabled": true}` (needs `tenants:update`, Admin).

Also set `BADGE_TOKEN_SECRET` (signs the badge QR; separate from
`QR_TOKEN_ENCRYPTION_KEY`) and optionally `BADGE_SCAN_RATE_LIMIT`
(default `30/minute`, per IP). See `docs/features/configuration.md`.

## Endpoints (`/api/v1/checkin`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/search?q=` | `visitors:print_badge` | Find visits by name, phone (digits-only), `trackingId`, or numeric check-in code. Branch-scoped, paginated, read-only. |
| POST | `/{visit_id}/verify-id` | `visitors:print_badge` | Reception confirms the physical ID. Idempotent (keeps the first timestamp). |
| POST | `/{visit_id}/badge` | `visitors:print_badge` | First print; returns `application/pdf`. Accepts `Idempotency-Key`. |
| GET | `/{visit_id}/badge?reason=` | `visitors:print_badge` | Reprint (see below). |
| POST | `/badge/check-out` | badge token | Scan checkout; closes the visit and deactivates the badge. Rate-limited. |
| POST | `/badge/re-enter` | badge token | Same-day re-entry for a visitor stepped out. Rate-limited. |

Scan endpoints take `{"token": "..."}` in the body (so it stays out of access
logs). The token is the credential; the tenant comes from its signed `tid` claim.

## Print gate

A badge prints only when the visit is `approved`/`checked_in`, has a photo, and
the ID is verified. Otherwise `409`, with every unmet condition named
(`visit_not_approved`, `photo_missing`, `id_not_verified`).

## Badge token

PyJWT HS256 with claims `sub` (visit), `tid` (tenant), `day` (tenant-local date
of printing), `jti`, `typ=badge`, `exp` (end of that day + 1h). A scan is valid
only if the signature checks, `day` is today in the tenant's timezone, and the
`badge_prints` row for that `jti` is still active. Every failure returns the same
`400 Invalid badge token`.

## Reprint policy

`GET /{visit_id}/badge?reason=lost` — a reason (1-255 chars) is mandatory, there is
no cap on reprints, the previous `jti` is deactivated and a new one issued in one
transaction, and the response is `Cache-Control: no-store`. **It is a state-changing
GET** (specified that way); `POST /{visit_id}/badge/reprint` would be safer under
prefetching and caches.

## Data

`badge_prints` (tenant schema, append-only): `visit_id`, `printed_by_user_id`,
`printed_at`, `jti` (unique), `day`, `active`, `reprint_reason`. The only update
ever made is `active` true -> false; a partial unique index allows one active
badge per visit. `invitations.id_verified_at` / `id_verified_by_user_id` record the
ID confirmation.

## Audit

`badge_printed`, `badge_reprinted`, `badge_checked_out`, `badge_re_entered`,
`visit_id_verified`, `tenant_settings_updated` — written by background tasks. Entries
hold the `jti` and reason, never the token or ID numbers.

## Approval email

When the flow is on for the tenant, the visitor's approval **email** also carries a
"Please bring your ID" callout (`visit_confirmation.html/.txt`). SMS and WhatsApp
are unchanged. With the flow off the email is byte-identical to before.

## Known limitation

Scan checkout deactivates the badge, so a visitor checked out *by scan* cannot
re-enter by scan; re-entry applies to visits stepped out by a path that doesn't
deactivate the badge (e.g. reception's existing checkout).
